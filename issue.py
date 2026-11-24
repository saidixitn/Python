import os
import logging
from collections import defaultdict
from datetime import datetime, timezone

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from pymongo import MongoClient


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

EMPLOYER_ID = "6a904f26060e8f0b78b0dc81"

SPREADSHEET_ID = "1c3WqKgewVn0mqQTsH4pQzuR8P9JK6xI5QJ2aXLsekQk"

GOOGLE_CREDENTIALS_FILE = os.getenv(
    "GOOGLE_CREDENTIALS_FILE",
    "credentials.json"
)

CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"

PROD_DATABASE = "prod_jobiak_ai"

JOB_COLLECTION = "job"
ANALYTICS_COLLECTION = "userAnalytics"

SHEET_NAME = "issue stats"

BATCH_SIZE = 2000

# Issue date: 18 October 2026, 00:00 UTC
ISSUE_DATE = datetime(2026, 10, 18, tzinfo=timezone.utc)

GOOGLE_VIEW_FILTER = {
    "employerId": EMPLOYER_ID,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True,
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("issue_stats")


# ============================================================
# CONNECTIONS
# ============================================================

def connect_mongodb():

    if not MONGO_URI:
        raise ValueError("MONGO_URI is missing from .env")

    bootstrap = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000
    )

    bootstrap.admin.command("ping")

    creds = bootstrap[CREDS_DATABASE][CREDS_COLLECTION].find_one(
        {"domain": PROD_DATABASE},
        {"_id": 0, "mongo_uri": 1}
    )

    if not creds or not creds.get("mongo_uri"):
        bootstrap.close()
        raise ValueError(
            f"Mongo URI not found for {PROD_DATABASE}"
        )

    target = MongoClient(
        creds["mongo_uri"],
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000
    )

    target.admin.command("ping")
    bootstrap.close()

    logger.info("Connected to MongoDB: %s", PROD_DATABASE)

    return target, target[PROD_DATABASE]


def connect_google_sheet():

    if not os.path.isfile(GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Google credentials not found: {GOOGLE_CREDENTIALS_FILE}"
        )

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )

    spreadsheet = gspread.authorize(credentials).open_by_key(
        SPREADSHEET_ID
    )

    logger.info("Connected to Google Sheet: %s", spreadsheet.title)

    return spreadsheet


# ============================================================
# HELPERS
# ============================================================

def safe_text(value):

    return "" if value is None else str(value).strip()


def safe_key(value):

    return safe_text(value)


def parse_datetime(value):

    if isinstance(value, datetime):

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    if isinstance(value, str) and value.strip():

        try:
            parsed = datetime.fromisoformat(
                value.strip().replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)

            return parsed.astimezone(timezone.utc)

        except ValueError:
            return None

    return None


def normalized_location(value):

    value = " ".join(safe_text(value).split())

    return value if value else "Unknown"


def get_job_key(job):

    return (
        safe_key(job.get("jobId"))
        or safe_key(job.get("clientJobId"))
        or safe_key(job.get("jobPubJobId"))
        or job["_reportJobKey"]
    )


# ============================================================
# JOB CLASSIFICATION
# ============================================================

def classify_job(job):

    if not job:
        return "Unmatched"

    status = safe_text(job.get("status")).lower()

    active = job.get("isActive")

    if status == "posted" and active is True:
        return "Posted"

    if status in {"removed", "expired", "deleted"} or active is False:
        return "Expired"

    return "Other / Unknown"


# ============================================================
# FETCH JOBS AND BUILD ID LOOKUPS
# ============================================================

def fetch_jobs(database):

    projection = {
        "_id": 0,
        "jobId": 1,
        "clientJobId": 1,
        "jobPubJobId": 1,
        "title": 1,
        "location": 1,
        "status": 1,
        "isActive": 1,
        "datePosted": 1,
    }

    cursor = database[JOB_COLLECTION].find(
        {"employerId": EMPLOYER_ID},
        projection,
        batch_size=BATCH_SIZE
    )

    jobs = []

    jobs_by_alias = defaultdict(dict)

    jobs_by_id = {}

    try:

        for index, job in enumerate(cursor):

            job["_reportJobKey"] = (
                safe_key(job.get("jobId"))
                or safe_key(job.get("clientJobId"))
                or safe_key(job.get("jobPubJobId"))
                or f"job_row_{index}"
            )

            jobs.append(job)

            job_id = safe_key(job.get("jobId"))

            if job_id:
                jobs_by_id[job_id] = job

            for field in (
                "jobId",
                "clientJobId",
                "jobPubJobId"
            ):

                alias = safe_key(job.get(field))

                if alias:

                    alias_key = job["_reportJobKey"]

                    jobs_by_alias[alias][alias_key] = job

    finally:
        cursor.close()

    logger.info("Total job documents loaded: %s", len(jobs))

    return jobs, jobs_by_alias, jobs_by_id


# ============================================================
# MATCH ANALYTICS TO JOBS
# ============================================================

def match_job(analytics, jobs_by_alias, jobs_by_id):

    for field in ("jobPubJobId", "childJobId"):

        key = safe_key(analytics.get(field))

        if not key:
            continue

        # First priority: exact jobId match
        if key in jobs_by_id:
            return jobs_by_id[key], False

        # Second priority: match against all job aliases
        matches = list(jobs_by_alias.get(key, {}).values())

        if len(matches) == 1:
            return matches[0], False

        if len(matches) > 1:
            return None, True

    return None, False


# ============================================================
# CALCULATE BEFORE / AFTER ISSUE STATISTICS
# ============================================================

def calculate_stats(database, jobs, jobs_by_alias, jobs_by_id):

    stats = {
        "Before Issue": {
            "posted_jobs": 0,
            "posted_locations": set(),
            "posted_views": 0,
            "posted_jobs_with_views": set(),
            "posted_locations_with_views": set(),

            "expired_jobs": 0,
            "expired_locations": set(),
            "expired_views": 0,
            "expired_jobs_with_views": set(),
            "expired_locations_with_views": set(),
        },

        "After Issue": {
            "posted_jobs": 0,
            "posted_locations": set(),
            "posted_views": 0,
            "posted_jobs_with_views": set(),
            "posted_locations_with_views": set(),

            "expired_jobs": 0,
            "expired_locations": set(),
            "expired_views": 0,
            "expired_jobs_with_views": set(),
            "expired_locations_with_views": set(),
        }
    }

    missing_date_jobs = 0
    other_status_jobs = 0

    # --------------------------------------------------------
    # 1. COUNT JOBS AND ALL DISTINCT LOCATIONS
    # --------------------------------------------------------

    for job in jobs:

        posted_date = parse_datetime(job.get("datePosted"))

        if not posted_date:
            missing_date_jobs += 1
            continue

        if posted_date < ISSUE_DATE:
            period = "Before Issue"
        else:
            period = "After Issue"

        classification = classify_job(job)

        location = normalized_location(job.get("location"))

        if classification == "Posted":

            stats[period]["posted_jobs"] += 1

            if location != "Unknown":
                stats[period]["posted_locations"].add(location)

        elif classification == "Expired":

            stats[period]["expired_jobs"] += 1

            if location != "Unknown":
                stats[period]["expired_locations"].add(location)

        else:

            other_status_jobs += 1

    logger.info("Job counts and all location counts calculated")

    # --------------------------------------------------------
    # 2. COUNT GOOGLE VIEWS, JOBS WITH VIEWS AND LOCATIONS
    #    WITH VIEWS
    # --------------------------------------------------------

    projection = {
        "_id": 0,
        "jobPubJobId": 1,
        "childJobId": 1,
    }

    cursor = database[ANALYTICS_COLLECTION].find(
        GOOGLE_VIEW_FILTER,
        projection,
        batch_size=BATCH_SIZE
    )

    total_views = 0
    unmatched_views = 0
    ambiguous_views = 0
    matched_views = 0

    try:

        for analytics in cursor:

            total_views += 1

            job, ambiguous = match_job(
                analytics,
                jobs_by_alias,
                jobs_by_id
            )

            if ambiguous:
                ambiguous_views += 1

            if not job:
                unmatched_views += 1
                continue

            posted_date = parse_datetime(job.get("datePosted"))

            if not posted_date:
                continue

            if posted_date < ISSUE_DATE:
                period = "Before Issue"
            else:
                period = "After Issue"

            classification = classify_job(job)

            job_key = get_job_key(job)

            location = normalized_location(job.get("location"))

            if classification == "Posted":

                stats[period]["posted_views"] += 1

                # Count each job only once
                stats[period]["posted_jobs_with_views"].add(
                    job_key
                )

                # Count each location only once,
                # but only when a posted job has a view
                if location != "Unknown":

                    stats[period]["posted_locations_with_views"].add(
                        location
                    )

                matched_views += 1

            elif classification == "Expired":

                stats[period]["expired_views"] += 1

                # Count each job only once
                stats[period]["expired_jobs_with_views"].add(
                    job_key
                )

                # Count each location only once,
                # but only when an expired job has a view
                if location != "Unknown":

                    stats[period]["expired_locations_with_views"].add(
                        location
                    )

                matched_views += 1

    finally:
        cursor.close()

    logger.info("Google view calculations completed")

    return {
        "stats": stats,
        "total_views": total_views,
        "matched_views": matched_views,
        "unmatched_views": unmatched_views,
        "ambiguous_views": ambiguous_views,
        "missing_date_jobs": missing_date_jobs,
        "other_status_jobs": other_status_jobs,
    }


# ============================================================
# CREATE / UPDATE ISSUE STATS TAB
# ============================================================

def write_to_sheet(spreadsheet, result):

    try:

        worksheet = spreadsheet.worksheet(SHEET_NAME)

    except gspread.WorksheetNotFound:

        worksheet = spreadsheet.add_worksheet(
            title=SHEET_NAME,
            rows=20,
            cols=3
        )

    before = result["stats"]["Before Issue"]
    after = result["stats"]["After Issue"]

    rows = [

        ["Metric", "Before Issue", "After Issue"],

        [
            "Posted Jobs",
            before["posted_jobs"],
            after["posted_jobs"]
        ],

        [
            "Expired Jobs",
            before["expired_jobs"],
            after["expired_jobs"]
        ],

        [
            "Posted Jobs with Views",
            len(before["posted_jobs_with_views"]),
            len(after["posted_jobs_with_views"])
        ],

        [
            "Expired Jobs with Views",
            len(before["expired_jobs_with_views"]),
            len(after["expired_jobs_with_views"])
        ],

        [
            "Posted Locations",
            len(before["posted_locations"]),
            len(after["posted_locations"])
        ],

        [
            "Expired Locations",
            len(before["expired_locations"]),
            len(after["expired_locations"])
        ],

        [
            "Locations with Views (Posted)",
            len(before["posted_locations_with_views"]),
            len(after["posted_locations_with_views"])
        ],

        [
            "Locations with Views (Expired)",
            len(before["expired_locations_with_views"]),
            len(after["expired_locations_with_views"])
        ],

        [
            "Views for Posted Jobs",
            before["posted_views"],
            after["posted_views"]
        ],

        [
            "Views for Expired Jobs",
            before["expired_views"],
            after["expired_views"]
        ],
    ]

    # Clear and write all metrics
    worksheet.clear()

    worksheet.update(
        range_name="A1",
        values=rows,
        value_input_option="USER_ENTERED"
    )

    worksheet.freeze(rows=1)

    # Header formatting
    worksheet.format("A1:C1", {
        "backgroundColor": {
            "red": 0.12,
            "green": 0.28,
            "blue": 0.48
        },
        "textFormat": {
            "bold": True,
            "foregroundColor": {
                "red": 1,
                "green": 1,
                "blue": 1
            }
        },
        "horizontalAlignment": "CENTER"
    })

    worksheet.format("A2:A11", {
        "textFormat": {"bold": True}
    })

    # Column widths using Google Sheets API
    spreadsheet.batch_update({
        "requests": [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": 1
                    },
                    "properties": {"pixelSize": 270},
                    "fields": "pixelSize"
                }
            },
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 1,
                        "endIndex": 3
                    },
                    "properties": {"pixelSize": 180},
                    "fields": "pixelSize"
                }
            }
        ]
    })

    logger.info("Updated Google Sheet tab: %s", SHEET_NAME)


# ============================================================
# MAIN
# ============================================================

def main():

    mongo_client = None

    try:

        # Connect to MongoDB and Google Sheets
        mongo_client, database = connect_mongodb()

        spreadsheet = connect_google_sheet()

        # Fetch jobs and build matching lookups
        jobs, jobs_by_alias, jobs_by_id = fetch_jobs(database)

        # Calculate all statistics
        result = calculate_stats(
            database,
            jobs,
            jobs_by_alias,
            jobs_by_id
        )

        # Write results to Google Sheet
        write_to_sheet(spreadsheet, result)

        # Console summary
        before = result["stats"]["Before Issue"]
        after = result["stats"]["After Issue"]

        logger.info("=" * 60)
        logger.info("ISSUE STATS COMPLETED")
        logger.info("-" * 60)

        logger.info("BEFORE ISSUE")

        logger.info(
            "Posted Jobs: %s | All Locations: %s | Jobs with Views: %s | Locations with Views: %s | Views: %s",
            before["posted_jobs"],
            len(before["posted_locations"]),
            len(before["posted_jobs_with_views"]),
            len(before["posted_locations_with_views"]),
            before["posted_views"]
        )

        logger.info(
            "Expired Jobs: %s | All Locations: %s | Jobs with Views: %s | Locations with Views: %s | Views: %s",
            before["expired_jobs"],
            len(before["expired_locations"]),
            len(before["expired_jobs_with_views"]),
            len(before["expired_locations_with_views"]),
            before["expired_views"]
        )

        logger.info("-" * 60)

        logger.info("AFTER ISSUE")

        logger.info(
            "Posted Jobs: %s | All Locations: %s | Jobs with Views: %s | Locations with Views: %s | Views: %s",
            after["posted_jobs"],
            len(after["posted_locations"]),
            len(after["posted_jobs_with_views"]),
            len(after["posted_locations_with_views"]),
            after["posted_views"]
        )

        logger.info(
            "Expired Jobs: %s | All Locations: %s | Jobs with Views: %s | Locations with Views: %s | Views: %s",
            after["expired_jobs"],
            len(after["expired_locations"]),
            len(after["expired_jobs_with_views"]),
            len(after["expired_locations_with_views"]),
            after["expired_views"]
        )

        logger.info("-" * 60)
        logger.info("Total Google views scanned: %s", result["total_views"])
        logger.info("Matched views: %s", result["matched_views"])
        logger.info("Unmatched views: %s", result["unmatched_views"])
        logger.info("Ambiguous views: %s", result["ambiguous_views"])
        logger.info("Jobs missing datePosted: %s", result["missing_date_jobs"])
        logger.info("=" * 60)

    finally:

        if mongo_client:
            mongo_client.close()


if __name__ == "__main__":
    main()