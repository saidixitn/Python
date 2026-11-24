
import os
import re
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

EMPLOYER_ID = "6a8871d1060e8f0b78b0dc69"

TARGET_DATABASE = "prod_jobiak_ai"
JOB_COLLECTION = "job"
ANALYTICS_COLLECTION = "userAnalytics"

CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"

GOOGLE_SHEET_ID = "1y9cZZslDri14RBAefdwkYSrvbx5NurpZFEQ3MfM9moM"
WORKSHEET_NAME = "concentrix - duplicates"
GOOGLE_CREDENTIALS_FILE = "credentials.json"

# Title-level fallback view-count window (UTC).
TITLE_VIEWS_START = datetime(2026, 9, 1, tzinfo=timezone.utc)
TITLE_VIEWS_END = datetime(2026, 10, 30, tzinfo=timezone.utc)

# Only active, posted jobs are considered for duplicate analysis.
JOB_FILTER = {
    "employerId": EMPLOYER_ID,
    "status": "posted",
    "isActive": True,
}

# These filters apply to both direct job views and title-level views.
GOOGLE_VIEW_FILTER = {
    "employerId": EMPLOYER_ID,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True,
}

OUTPUT_HEADERS = [
    "Duplicate Group",
    "Location",
    "Job ID",
    "Job Title",
    "datePosted",
    "Submitted URL",
    "job_views",
    "title_views",
    "views_used_for_decision",
    "view_source",
    "Action",
    "Reason",
    "Checked At (UTC)",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# MONGODB CONNECTION
# ============================================================

def connect_mongodb():
    """
    MONGO_URI connects to the MongoDB instance containing
    mongo_creds.creds. The target database URI is retrieved
    from the matching credentials document.
    """
    bootstrap_uri = os.getenv("MONGO_URI")

    if not bootstrap_uri:
        raise ValueError(
            "MONGO_URI is missing. Add it to your .env file."
        )

    bootstrap_client = MongoClient(
        bootstrap_uri,
        serverSelectionTimeoutMS=15000,
    )

    # Confirm the initial connection works.
    bootstrap_client.admin.command("ping")

    creds_collection = bootstrap_client[
        CREDS_DATABASE
    ][CREDS_COLLECTION]

    credentials_doc = creds_collection.find_one(
        {"domain": TARGET_DATABASE},
        {"mongo_uri": 1},
    )

    if not credentials_doc or not credentials_doc.get("mongo_uri"):
        bootstrap_client.close()
        raise ValueError(
            f"Could not find mongo_uri in "
            f"{CREDS_DATABASE}.{CREDS_COLLECTION} "
            f"for domain={TARGET_DATABASE!r}."
        )

    target_uri = credentials_doc["mongo_uri"]

    target_client = MongoClient(
        target_uri,
        serverSelectionTimeoutMS=15000,
    )

    target_client.admin.command("ping")

    # Close the bootstrap connection if it is separate.
    if target_uri != bootstrap_uri:
        bootstrap_client.close()

    database = target_client[TARGET_DATABASE]

    logger.info("Connected to MongoDB database: %s", TARGET_DATABASE)

    return target_client, database


# ============================================================
# GOOGLE SHEETS
# ============================================================

def connect_google_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=1000,
            cols=len(OUTPUT_HEADERS),
        )
        logger.info("Created worksheet: %s", WORKSHEET_NAME)

    return worksheet


def write_report(worksheet, rows):
    """
    Replaces the contents of the target worksheet only.
    Other worksheets in the spreadsheet are not changed.
    """
    worksheet.clear()

    values = [OUTPUT_HEADERS] + rows

    # Ensure the worksheet has enough rows and columns.
    required_rows = max(len(values), 1)
    required_cols = len(OUTPUT_HEADERS)

    if worksheet.row_count < required_rows:
        worksheet.add_rows(required_rows - worksheet.row_count)

    if worksheet.col_count < required_cols:
        worksheet.add_cols(required_cols - worksheet.col_count)

    worksheet.update(
        range_name="A1",
        values=values,
        value_input_option="USER_ENTERED",
    )

    worksheet.freeze(rows=1)
    worksheet.format(
        "A1:M1",
        {
            "textFormat": {"bold": True},
            "wrapStrategy": "WRAP",
        },
    )

    logger.info(
        "Wrote %s job rows to worksheet %r.",
        len(rows),
        WORKSHEET_NAME,
    )


# ============================================================
# DATE AND VALUE FORMATTING
# ============================================================

def format_date(value):
    """Convert MongoDB date values to a readable UTC string."""
    if value is None:
        return ""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        return value.strftime("%Y-%m-%d")

    return str(value)


def stringify(value):
    if value is None:
        return ""
    return str(value)


# ============================================================
# FETCH ACTIVE JOBS
# ============================================================

def fetch_active_jobs(database):
    collection = database[JOB_COLLECTION]

    projection = {
        "_id": 0,
        "jobId": 1,
        "title": 1,
        "location": 1,
        "submittedUrl": 1,
        "datePosted": 1,
    }

    jobs = list(
        collection.find(JOB_FILTER, projection)
    )

    # Ignore records without jobId and deduplicate repeated
    # jobId values in the returned dataset.
    unique_jobs = {}
    for job in jobs:
        job_id = job.get("jobId")

        if job_id is None:
            continue

        unique_jobs[str(job_id)] = job

    result = list(unique_jobs.values())

    logger.info("Fetched %s active posted jobs.", len(result))
    return result


# ============================================================
# FETCH DIRECT JOB VIEW COUNTS
# ============================================================

def fetch_job_view_counts(database, jobs):
    """
    Count valid Google-originated analytics records by
    childJobId. No date restriction is applied to direct views.
    """
    if not jobs:
        return {}

    job_ids = [job["jobId"] for job in jobs]

    match_filter = {
        **GOOGLE_VIEW_FILTER,
        "childJobId": {"$in": job_ids},
    }

    pipeline = [
        {"$match": match_filter},
        {
            "$group": {
                "_id": "$childJobId",
                "views": {"$sum": 1},
            }
        },
    ]

    results = database[ANALYTICS_COLLECTION].aggregate(
        pipeline,
        allowDiskUse=True,
    )

    counts = {
        str(item["_id"]): int(item["views"])
        for item in results
        if item.get("_id") is not None
    }

    logger.info(
        "Fetched direct view counts for %s jobs.",
        len(counts),
    )

    return counts


# ============================================================
# FETCH TITLE-LEVEL FALLBACK VIEW COUNTS
# ============================================================

def fetch_title_view_counts(database):
    """
    Count valid Google-originated views during the configured
    date window, joined to the job collection by:
        userAnalytics.childJobId == job.jobId

    Results are grouped by job title. These counts are used
    for decision-making only when every job in a duplicate
    group has zero direct job_views.
    """
    pipeline = [
        {
            "$match": {
                **GOOGLE_VIEW_FILTER,
                "createdDt": {
                    "$gt": TITLE_VIEWS_START,
                    "$lt": TITLE_VIEWS_END,
                },
            }
        },
        {
            "$lookup": {
                "from": JOB_COLLECTION,
                "localField": "childJobId",
                "foreignField": "jobId",
                "as": "jobDetails",
            }
        },
        {"$unwind": "$jobDetails"},
        {
            "$match": {
                "jobDetails.employerId": EMPLOYER_ID,
            }
        },
        {
            "$group": {
                "_id": "$jobDetails.title",
                "views": {"$sum": 1},
            }
        },
    ]

    results = database[ANALYTICS_COLLECTION].aggregate(
        pipeline,
        allowDiskUse=True,
    )

    counts = {
        str(item["_id"]): int(item["views"])
        for item in results
        if item.get("_id") is not None
    }

    logger.info(
        "Fetched title-level view counts for %s titles.",
        len(counts),
    )

    return counts


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def normalize_location(location):
    """
    Normalize case, punctuation, and whitespace for location
    comparison. Locations must match after normalization.
    """
    if not location:
        return ""

    value = str(location).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_title(title):
    if not title:
        return ""

    value = str(title).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[/|_,-]+", " ", value)
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


GENERIC_TITLE_WORDS = {
    "a", "an", "and", "at", "for", "in", "of", "the", "to",
    "i", "ii", "iii", "iv", "1", "2", "3",
    "job", "position", "role",
    "full", "time", "part", "temporary", "seasonal",
    "remote", "hybrid", "onsite", "on", "site",
    "entry", "level", "senior", "junior",
    "associate", "specialist", "representative", "rep",
    "professional", "experienced",
}


ROLE_FAMILY_KEYWORDS = {
    "customer_service": {
        "customer service",
        "customer support",
        "customer care",
        "call center",
        "contact center",
        "client support",
        "client services",
        "customer experience",
    },
    "sales": {
        "sales representative",
        "sales associate",
        "account executive",
        "business development",
        "inside sales",
        "outside sales",
    },
    "insurance": {
        "insurance agent",
        "insurance sales",
        "insurance representative",
        "claims adjuster",
        "claims representative",
    },
    "technical_support": {
        "technical support",
        "help desk",
        "it support",
        "service desk",
        "desktop support",
    },
    "administration": {
        "administrative assistant",
        "office assistant",
        "office administrator",
        "receptionist",
        "front desk",
    },
    "human_resources": {
        "human resources",
        "hr specialist",
        "recruiter",
        "talent acquisition",
    },
    "finance_accounting": {
        "accountant",
        "accounting",
        "bookkeeper",
        "financial analyst",
        "payroll specialist",
    },
    "healthcare": {
        "registered nurse",
        "licensed practical nurse",
        "medical assistant",
        "patient care",
        "healthcare assistant",
        "clinical specialist",
    },
    "engineering": {
        "software engineer",
        "software developer",
        "data engineer",
        "systems engineer",
        "network engineer",
        "quality engineer",
    },
    "management": {
        "team leader",
        "team lead",
        "supervisor",
        "operations manager",
        "project manager",
        "program manager",
    },
}


def role_families(title):
    """
    Return any recognized role families for a title.
    This prevents unrelated jobs from being grouped merely
    because they share a location.
    """
    normalized = normalize_title(title)
    families = set()

    for family, phrases in ROLE_FAMILY_KEYWORDS.items():
        for phrase in phrases:
            phrase = normalize_title(phrase)

            if re.search(
                r"\b" + re.escape(phrase) + r"\b",
                normalized,
            ):
                families.add(family)
                break

    return families


def title_tokens(title):
    tokens = set(normalize_title(title).split())
    return tokens - GENERIC_TITLE_WORDS


def title_similarity(title_a, title_b):
    normalized_a = normalize_title(title_a)
    normalized_b = normalize_title(title_b)

    if not normalized_a or not normalized_b:
        return 0.0

    return SequenceMatcher(
        None,
        normalized_a,
        normalized_b,
    ).ratio()


def are_duplicate_candidates(job_a, job_b):
    """
    A pair is considered a duplicate candidate only when:
      1. Both jobs have the same normalized location, and
      2. Their titles are similar or share a recognized role
         family with meaningful title-token overlap.

    This is a heuristic for review, not a guarantee that the
    postings are duplicates.
    """
    location_a = normalize_location(job_a.get("location"))
    location_b = normalize_location(job_b.get("location"))

    if not location_a or location_a != location_b:
        return False

    title_a = job_a.get("title", "")
    title_b = job_b.get("title", "")

    normalized_a = normalize_title(title_a)
    normalized_b = normalize_title(title_b)

    if not normalized_a or not normalized_b:
        return False

    if normalized_a == normalized_b:
        return True

    tokens_a = title_tokens(title_a)
    tokens_b = title_tokens(title_b)

    if not tokens_a or not tokens_b:
        return False

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    jaccard = len(intersection) / len(union) if union else 0
    overlap_a = len(intersection) / len(tokens_a)
    overlap_b = len(intersection) / len(tokens_b)
    similarity = title_similarity(title_a, title_b)

    families_a = role_families(title_a)
    families_b = role_families(title_b)
    shared_family = bool(families_a & families_b)

    # High title similarity can identify titles with minor
    # wording differences.
    if similarity >= 0.78:
        return True

    # Different titles in the same family need meaningful
    # token overlap to avoid grouping every role in a family.
    if shared_family and (
        jaccard >= 0.30
        or overlap_a >= 0.60
        or overlap_b >= 0.60
    ):
        return True

    # For titles without a shared recognized family, require
    # stronger token overlap.
    if (
        jaccard >= 0.60
        and similarity >= 0.55
    ):
        return True

    return False


def find_duplicate_groups(jobs):
    """
    Group connected duplicate candidates using a union-find
    approach. Every returned group contains at least two jobs.
    """
    if len(jobs) < 2:
        return []

    parent = list(range(len(jobs)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(index_a, index_b):
        root_a = find(index_a)
        root_b = find(index_b)

        if root_a != root_b:
            parent[root_b] = root_a

    # Compare jobs only within the same normalized location.
    by_location = defaultdict(list)

    for index, job in enumerate(jobs):
        location_key = normalize_location(job.get("location"))

        if location_key:
            by_location[location_key].append(index)

    for indices in by_location.values():
        for position, index_a in enumerate(indices):
            for index_b in indices[position + 1:]:
                if are_duplicate_candidates(
                    jobs[index_a],
                    jobs[index_b],
                ):
                    union(index_a, index_b)

    grouped = defaultdict(list)

    for index, job in enumerate(jobs):
        grouped[find(index)].append(job)

    duplicate_groups = [
        group
        for group in grouped.values()
        if len(group) > 1
    ]

    # Stable order for repeatable reports.
    duplicate_groups.sort(
        key=lambda group: (
            normalize_location(group[0].get("location")),
            normalize_title(group[0].get("title")),
        )
    )

    logger.info(
        "Identified %s duplicate candidate groups.",
        len(duplicate_groups),
    )

    return duplicate_groups


# ============================================================
# GROUP DECISION LOGIC
# ============================================================

def decide_group(
    group,
    group_number,
    job_view_counts,
    title_view_counts,
    checked_at,
):
    """
    Decision rules:
      - If at least one job has direct job_views > 0, compare
        direct job_views across the group.
      - If every job has zero direct job_views, compare
        title_views instead.
      - Highest count: ACTIVE.
      - Lower count: EXPIRE (recommendation only).
      - Ties or all-zero comparison: REVIEW.
    """
    group_id = f"DUP-{group_number:04d}"

    direct_counts = [
        job_view_counts.get(str(job["jobId"]), 0)
        for job in group
    ]

    use_title_fallback = all(
        count == 0 for count in direct_counts
    )

    if use_title_fallback:
        decision_counts = [
            title_view_counts.get(
                str(job.get("title", "")),
                0,
            )
            for job in group
        ]
        view_source = "title_views"
    else:
        decision_counts = direct_counts
        view_source = "job_views"

    highest_count = max(decision_counts, default=0)
    highest_indexes = [
        index
        for index, count in enumerate(decision_counts)
        if count == highest_count
    ]

    rows = []

    for index, job in enumerate(group):
        job_id = stringify(job.get("jobId"))
        title = stringify(job.get("title"))
        location = stringify(job.get("location"))

        direct_views = job_view_counts.get(job_id, 0)
        title_views = title_view_counts.get(title, 0)
        decision_views = decision_counts[index]

        if highest_count == 0:
            action = "REVIEW"
            reason = (
                "All jobs in this duplicate group have zero "
                "views under the selected decision source."
            )
        elif len(highest_indexes) > 1:
            action = "REVIEW"
            reason = (
                "Multiple jobs share the highest view count; "
                "there is no unique winner."
            )
        elif index in highest_indexes:
            action = "ACTIVE"
            reason = (
                f"Highest {view_source} in the duplicate group "
                f"({decision_views} views)."
            )
        else:
            action = "EXPIRE"
            reason = (
                f"Lower {view_source} than the leading job "
                f"({decision_views} vs {highest_count} views). "
                "Recommendation only; no job was expired."
            )

        rows.append([
            group_id,
            location,
            job_id,
            title,
            format_date(job.get("datePosted")),
            stringify(job.get("submittedUrl")),
            direct_views,
            title_views,
            decision_views,
            view_source,
            action,
            reason,
            checked_at,
        ])

    return rows


# ============================================================
# MAIN
# ============================================================

def main():
    mongo_client = None

    try:
        mongo_client, database = connect_mongodb()
        worksheet = connect_google_sheet()

        jobs = fetch_active_jobs(database)

        if not jobs:
            logger.warning(
                "No active posted jobs found for employer %s.",
                EMPLOYER_ID,
            )
            write_report(worksheet, [])
            return

        job_view_counts = fetch_job_view_counts(
            database,
            jobs,
        )

        title_view_counts = fetch_title_view_counts(
            database,
        )

        duplicate_groups = find_duplicate_groups(jobs)

        checked_at = datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")

        output_rows = []

        for group_number, group in enumerate(
            duplicate_groups,
            start=1,
        ):
            output_rows.extend(
                decide_group(
                    group=group,
                    group_number=group_number,
                    job_view_counts=job_view_counts,
                    title_view_counts=title_view_counts,
                    checked_at=checked_at,
                )
            )

        write_report(worksheet, output_rows)

        action_counts = Counter(
            row[10] for row in output_rows
        )

        logger.info("Report completed.")
        logger.info("Duplicate candidate groups: %s", len(duplicate_groups))
        logger.info("Jobs included in report: %s", len(output_rows))
        logger.info("ACTIVE recommendations: %s", action_counts["ACTIVE"])
        logger.info("EXPIRE recommendations: %s", action_counts["EXPIRE"])
        logger.info("REVIEW recommendations: %s", action_counts["REVIEW"])

    except (PyMongoError, gspread.exceptions.GSpreadException, ValueError) as exc:
        logger.exception("Report failed: %s", exc)
        raise

    finally:
        if mongo_client is not None:
            mongo_client.close()


if __name__ == "__main__":
    main()
