import os
import logging
from datetime import datetime, timezone

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

# Google Sheets
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_ID = "157RNJcQAPJIYnRkJrmZ02MbZswq2OS77evp3s6UN6dE"
DOMAINS_SHEET = "Domains"

# MongoDB credentials collection
CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"

# Jobicare database
JOBICARE_DATABASE = "jobicarenode_prod"
JOBICARE_COLLECTION = "Target_P4_Opt"

# Production database
PROD_DATABASE = "prod_jobiak_ai"
JOB_COLLECTION = "job"
ANALYTICS_COLLECTION = "userAnalytics"

MONGO_BATCH_SIZE = 500

# Google-originated view filters.
# Same filters as the Concentrix analytics script.
GOOGLE_VIEW_FILTER = {
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True,
}

# Title-level view window (UTC), matching the supplied Concentrix script.
# The end date is exclusive.
TITLE_VIEWS_START = datetime(2026, 9, 1, tzinfo=timezone.utc)
TITLE_VIEWS_END = datetime(2026, 10, 30, tzinfo=timezone.utc)

OUTPUT_HEADERS = [
    "Client",
    "EmployerId",
    "jobicare employerId",
    "jobId",
    "clientJobId",
    "Job Title",
    "Location",
    "Submitted URL",
    "Date Posted",
    "Valid Through",
    "Job Views",
    "Title Views",
    "Checked At (UTC)",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# MONGODB CONNECTIONS
# ============================================================

def connect_primary_mongodb():
    """Connect using MONGO_URI from the .env file."""
    if not MONGO_URI:
        raise ValueError("MONGO_URI is missing from the .env file.")

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000,
    )
    client.admin.command("ping")
    logger.info("Connected to primary MongoDB.")
    return client


def get_mongo_uris(primary_client):
    """Read the target database URIs from mongo_creds.creds."""
    collection = primary_client[CREDS_DATABASE][CREDS_COLLECTION]

    required_domains = [JOBICARE_DATABASE, PROD_DATABASE]
    mongo_uris = {}

    for domain in required_domains:
        document = collection.find_one(
            {"domain": domain},
            {"_id": 0, "mongo_uri": 1},
        )

        if not document or not document.get("mongo_uri"):
            raise ValueError(
                f"MongoDB URI not found for '{domain}' in "
                f"{CREDS_DATABASE}.{CREDS_COLLECTION}."
            )

        mongo_uris[domain] = document["mongo_uri"]
        logger.info("Retrieved MongoDB URI for %s.", domain)

    return mongo_uris


def connect_target_mongodb(mongo_uri, database_name):
    """Connect to a target MongoDB database."""
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000,
    )
    client.admin.command("ping")
    logger.info("Connected to database: %s", database_name)
    return client, client[database_name]


# ============================================================
# GOOGLE SHEETS
# ============================================================

def connect_google_sheets():
    if not os.path.isfile(GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Credentials file not found: {GOOGLE_CREDENTIALS_FILE}"
        )

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    google_client = gspread.authorize(credentials)
    spreadsheet = google_client.open_by_key(SPREADSHEET_ID)
    logger.info("Connected to Google Sheets.")
    return spreadsheet


def get_employers(spreadsheet):
    """
    Read employer mappings from the Domains worksheet.

    Required columns:
      Client
      EmployerId
      jobicare employerId
    """
    worksheet = spreadsheet.worksheet(DOMAINS_SHEET)
    records = worksheet.get_all_records()

    employers = []
    seen = set()

    for row in records:
        client_name = str(row.get("Client", "")).strip()
        employer_id = str(row.get("EmployerId", "")).strip()
        jobicare_employer_id = str(
            row.get("jobicare employerId", "")
        ).strip()

        if not client_name:
            continue

        if not employer_id or not jobicare_employer_id:
            logger.warning(
                "Skipping '%s': employer ID mapping is incomplete.",
                client_name,
            )
            continue

        if len(client_name) > 100:
            logger.warning(
                "Skipping '%s': worksheet name exceeds 100 characters.",
                client_name,
            )
            continue

        key = (client_name, employer_id, jobicare_employer_id)
        if key in seen:
            continue

        seen.add(key)
        employers.append({
            "client": client_name,
            "employer_id": employer_id,
            "jobicare_employer_id": jobicare_employer_id,
        })

    logger.info("Loaded %s employer mappings.", len(employers))
    return employers


# ============================================================
# QUERY 1: GET EXPIRED FEED JOB UNIQUE KEYS
# ============================================================

def get_expired_feed_unique_keys(jobicare_db, jobicare_employer_id):
    """
    Find feed-expired jobs in:
      jobicarenode_prod.Target_P4_Opt

    Conditions:
      employerId = configured Jobicare employer ID
      job_status = 3
      gpost = 3

    Each uniqueKey is treated as a clientJobId to exclude from
    the active production jobs query.
    """
    collection = jobicare_db[JOBICARE_COLLECTION]

    query = {
        "employerId": jobicare_employer_id,
        "job_status": 3,
        "gpost": 3,
    }
    projection = {"_id": 0, "uniqueKey": 1}

    unique_keys = []
    cursor = collection.find(
        query,
        projection,
        batch_size=MONGO_BATCH_SIZE,
    )

    try:
        for document in cursor:
            unique_key = document.get("uniqueKey")
            if isinstance(unique_key, str) and unique_key.strip():
                unique_keys.append(unique_key.strip())
    finally:
        cursor.close()

    # Deduplicate while preserving order.
    unique_keys = list(dict.fromkeys(unique_keys))

    logger.info(
        "%s: found %s expired-feed unique keys.",
        jobicare_employer_id,
        len(unique_keys),
    )
    return unique_keys


# ============================================================
# QUERY 2: GET ACTIVE JOBS EXCLUDING EXPIRED FEED JOBS
# ============================================================

def get_update_jobs(prod_db, employer_id, expired_client_job_ids):
    """
    Find active production jobs that are NOT expired in the feed.

    Conditions:
      employerId = configured production employer ID
      status = posted
      isActive = true
      clientJobId NOT IN expired feed uniqueKey values
    """
    collection = prod_db[JOB_COLLECTION]

    query = {
        "employerId": employer_id,
        "status": "posted",
        "isActive": True,
        "clientJobId": {
            "$nin": expired_client_job_ids,
        },
    }

    projection = {
        "_id": 0,
        "jobId": 1,
        "submittedUrl": 1,
        "title": 1,
        "location": 1,
        "clientJobId": 1,
        "datePosted": 1,
        "validThrough": 1,
    }

    jobs_by_id = {}
    cursor = collection.find(
        query,
        projection,
        batch_size=MONGO_BATCH_SIZE,
    )

    try:
        for job in cursor:
            job_id = job.get("jobId")
            if job_id is None:
                logger.warning("Skipping a job without jobId.")
                continue

            # Avoid duplicate jobId rows.
            jobs_by_id[str(job_id)] = job
    finally:
        cursor.close()

    jobs = list(jobs_by_id.values())

    logger.info(
        "%s: found %s active jobs eligible for update.",
        employer_id,
        len(jobs),
    )
    return jobs


# ============================================================
# QUERY 3: GET GOOGLE VIEW COUNTS FOR THE JOBS
# ============================================================

def fetch_google_view_counts(prod_db, employer_id, jobs):
    """
    Count Google-originated, non-bot analytics records by childJobId.

    Same direct job-view approach and filters as the supplied
    Concentrix script. No createdDt date restriction is applied.
    """
    if not jobs:
        return {}

    analytics_collection = prod_db[ANALYTICS_COLLECTION]
    job_ids = [job["jobId"] for job in jobs if job.get("jobId") is not None]

    counts = {}

    # Process job IDs in batches to keep the $in query manageable.
    for start in range(0, len(job_ids), MONGO_BATCH_SIZE):
        job_id_batch = job_ids[start:start + MONGO_BATCH_SIZE]

        match_filter = {
            **GOOGLE_VIEW_FILTER,
            "employerId": employer_id,
            "childJobId": {"$in": job_id_batch},
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

        results = analytics_collection.aggregate(
            pipeline,
            allowDiskUse=True,
        )

        for item in results:
            if item.get("_id") is not None:
                counts[str(item["_id"])] = int(item["views"])

    logger.info(
        "%s: fetched Google view counts for %s jobs.",
        employer_id,
        len(counts),
    )
    return counts


# ============================================================
# QUERY 4: GET TITLE-LEVEL GOOGLE VIEW COUNTS
# ============================================================

def fetch_title_view_counts(prod_db, employer_id):
    """Count Google views in the configured date window, join analytics
    to jobs using childJobId == jobId, filter by employer, and group by title.
    This follows the title-level fallback query in concentrix_expires.py.
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
        {"$match": {"jobDetails.employerId": employer_id}},
        {
            "$group": {
                "_id": "$jobDetails.title",
                "views": {"$sum": 1},
            }
        },
    ]

    results = prod_db[ANALYTICS_COLLECTION].aggregate(
        pipeline,
        allowDiskUse=True,
    )

    counts = {
        str(item["_id"]): int(item["views"])
        for item in results
        if item.get("_id") is not None
    }

    logger.info(
        "%s: fetched title-level Google views for %s titles.",
        employer_id,
        len(counts),
    )
    return counts


# ============================================================
# VALUE FORMATTING
# ============================================================

def format_value(value):
    if value is None:
        return ""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, bool):
        return str(value).lower()

    if isinstance(value, (str, int, float)):
        return value

    return str(value)


def prepare_output_rows(
    employer,
    jobs,
    job_view_counts,
    title_view_counts,
    checked_at,
):
    rows = []

    for job in jobs:
        job_id = job.get("jobId")

        rows.append([
            employer["client"],
            employer["employer_id"],
            employer["jobicare_employer_id"],
            format_value(job_id),
            format_value(job.get("clientJobId")),
            format_value(job.get("title")),
            format_value(job.get("location")),
            format_value(job.get("submittedUrl")),
            format_value(job.get("datePosted")),
            format_value(job.get("validThrough")),
            job_view_counts.get(str(job_id), 0),
            title_view_counts.get(str(job.get("title", "")), 0),
            checked_at,
        ])

    return rows


# ============================================================
# CLIENT WORKSHEETS
# ============================================================

def get_client_worksheet(spreadsheet, client_name):
    try:
        return spreadsheet.worksheet(client_name)
    except gspread.WorksheetNotFound:
        logger.info("Creating worksheet for client: %s", client_name)
        return spreadsheet.add_worksheet(
            title=client_name,
            rows=1000,
            cols=len(OUTPUT_HEADERS),
        )


def update_client_worksheet(spreadsheet, client_name, output_rows):
    """
    Replace only this client's worksheet.
    Other client worksheets and the Domains worksheet remain untouched.
    """
    worksheet = get_client_worksheet(spreadsheet, client_name)

    values = [OUTPUT_HEADERS, *output_rows]

    worksheet.resize(
        rows=max(1, len(values)),
        cols=len(OUTPUT_HEADERS),
    )
    worksheet.clear()

    worksheet.update(
        range_name="A1",
        values=values,
        value_input_option="RAW",
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
        "Updated worksheet '%s' with %s jobs.",
        client_name,
        len(output_rows),
    )


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    primary_client = None
    jobicare_client = None
    prod_client = None

    try:
        logger.info("=" * 65)
        logger.info("JOB UPDATE CANDIDATE REPORT STARTED")
        logger.info("=" * 65)

        # 1. Connect to the primary MongoDB instance.
        primary_client = connect_primary_mongodb()

        # 2. Retrieve target database connection strings.
        mongo_uris = get_mongo_uris(primary_client)

        # 3. Connect to Jobicare.
        jobicare_client, jobicare_db = connect_target_mongodb(
            mongo_uris[JOBICARE_DATABASE],
            JOBICARE_DATABASE,
        )

        # 4. Connect to production.
        prod_client, prod_db = connect_target_mongodb(
            mongo_uris[PROD_DATABASE],
            PROD_DATABASE,
        )

        # 5. Connect to Google Sheets and read employer mappings.
        spreadsheet = connect_google_sheets()
        employers = get_employers(spreadsheet)

        if not employers:
            raise RuntimeError(
                "No valid employer mappings found in the Domains worksheet."
            )

        checked_at = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        total_expired_keys = 0
        total_update_jobs = 0
        total_job_views = 0
        total_title_views = 0

        # 6. Process each employer.
        for employer in employers:
            client_name = employer["client"]
            employer_id = employer["employer_id"]
            jobicare_employer_id = employer["jobicare_employer_id"]

            logger.info("-" * 65)
            logger.info("Processing client: %s", client_name)

            # Query 1: Feed-expired jobs.
            expired_keys = get_expired_feed_unique_keys(
                jobicare_db,
                jobicare_employer_id,
            )
            total_expired_keys += len(expired_keys)

            # Query 2: Active production jobs excluding feed-expired jobs.
            update_jobs = get_update_jobs(
                prod_db,
                employer_id,
                expired_keys,
            )
            total_update_jobs += len(update_jobs)

            # Query 3: Google views for each eligible active job.
            job_view_counts = fetch_google_view_counts(
                prod_db,
                employer_id,
                update_jobs,
            )

            # Fetch title-level views independently for this employer.
            title_view_counts = fetch_title_view_counts(
                prod_db,
                employer_id,
            )

            total_job_views += sum(job_view_counts.values())
            total_title_views += sum(title_view_counts.values())

            # Prepare and write this client's worksheet.
            output_rows = prepare_output_rows(
                employer,
                update_jobs,
                job_view_counts,
                title_view_counts,
                checked_at,
            )

            update_client_worksheet(
                spreadsheet,
                client_name,
                output_rows,
            )

        # 7. Final execution summary.
        logger.info("=" * 65)
        logger.info("JOB UPDATE CANDIDATE REPORT COMPLETED")
        logger.info("Employers processed: %s", len(employers))
        logger.info("Expired feed unique keys: %s", total_expired_keys)
        logger.info("Active jobs eligible for update: %s", total_update_jobs)
        logger.info("Total direct job views: %s", total_job_views)
        logger.info("Total title-level views: %s", total_title_views)
        logger.info("=" * 65)

    except (PyMongoError, gspread.exceptions.GSpreadException, ValueError):
        logger.exception("JOB UPDATE CANDIDATE REPORT FAILED")
        raise

    except Exception:
        logger.exception("Unexpected failure in update report.")
        raise

    finally:
        for client in (prod_client, jobicare_client, primary_client):
            if client is not None:
                client.close()

        logger.info("MongoDB connections closed.")


if __name__ == "__main__":
    main()
