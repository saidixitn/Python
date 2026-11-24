
import os
import json
import time
import logging

from pathlib import Path
from datetime import datetime, timezone

import gspread
from gspread.exceptions import APIError
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from pymongo import MongoClient


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

# Google Sheets
GOOGLE_CREDENTIALS = "credentials.json"
SPREADSHEET_ID = "1y9cZZslDri14RBAefdwkYSrvbx5NurpZFEQ3MfM9moM"
DOMAINS_SHEET = "Domains"

# MongoDB credentials collection
CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"

# Jobicare database
JOBICARE_DATABASE = "jobicarenode_prod"
JOBICARE_COLLECTION = "Target_P4_Opt"

# Production database
PROD_DATABASE = "prod_jobiak_ai"
PROD_COLLECTION = "job"

# Analytics collection
ANALYTICS_COLLECTION = "userAnalytics"

# MongoDB batch size
MONGO_BATCH_SIZE = 500

# Title views date range (UTC)
# Start: September 1, 2026
# End: October 30, 2026 (exclusive)
TITLE_VIEWS_START = datetime(
    2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc
)

TITLE_VIEWS_END = datetime(
    2026, 10, 30, 0, 0, 0, tzinfo=timezone.utc
)

# Local checkpoint
CACHE_DIR = Path("expiry_run_cache")
CACHE_FILE = CACHE_DIR / "expiry_results.json"
CACHE_VERSION = 1

# Google Sheets output columns
OUTPUT_HEADERS = [
    "Client",
    "EmployerId",
    "jobicare employerId",
    "jobId",
    "Job Title",
    "Status",
    "Is Active",
    "Date Posted",
    "Job Views",
    "Title Views",
    "Checked At (UTC)",
]

# Google Sheets retry settings
SHEETS_MAX_RETRIES = 5
SHEETS_INITIAL_BACKOFF = 2


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# GOOGLE SHEETS RETRY HANDLER
# ============================================================

def sheets_request(function, *args, **kwargs):
    """
    Retry temporary Google Sheets API errors.

    Retries:
        429
        500
        502
        503
        504

    Does not retry permanent errors such as HTTP 400.
    """

    for attempt in range(1, SHEETS_MAX_RETRIES + 1):

        try:
            return function(*args, **kwargs)

        except APIError as error:

            response = getattr(error, "response", None)

            status_code = getattr(
                response,
                "status_code",
                None,
            )

            retryable_codes = {
                429,
                500,
                502,
                503,
                504,
            }

            if (
                status_code not in retryable_codes
                or attempt == SHEETS_MAX_RETRIES
            ):
                raise

            wait_time = (
                SHEETS_INITIAL_BACKOFF * (2 ** (attempt - 1))
            )

            logger.warning(
                "Google Sheets API error %s. "
                "Retrying in %s seconds. Attempt %s/%s.",
                status_code,
                wait_time,
                attempt,
                SHEETS_MAX_RETRIES,
            )

            time.sleep(wait_time)


# ============================================================
# MONGODB CONNECTION
# ============================================================

def connect_primary_mongodb():
    """Connect using the MongoDB URI stored in .env."""

    if not MONGO_URI:
        raise ValueError(
            "MONGO_URI is missing from the .env file."
        )

    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000,
    )

    client.admin.command("ping")

    logger.info("Connected to primary MongoDB.")

    return client


def get_mongo_uris(primary_client):
    """Retrieve target MongoDB URIs from mongo_creds.creds."""

    collection = primary_client[
        CREDS_DATABASE
    ][CREDS_COLLECTION]

    required_domains = [
        JOBICARE_DATABASE,
        PROD_DATABASE,
    ]

    mongo_uris = {}

    for domain in required_domains:

        document = collection.find_one(
            {"domain": domain},
            {
                "_id": 0,
                "mongo_uri": 1,
            },
        )

        if not document or not document.get("mongo_uri"):
            raise ValueError(
                f"MongoDB URI not found for '{domain}' "
                f"in {CREDS_DATABASE}.{CREDS_COLLECTION}."
            )

        mongo_uris[domain] = document["mongo_uri"]

        logger.info(
            "Retrieved MongoDB URI for %s.",
            domain,
        )

    return mongo_uris


def connect_target_mongodb(mongo_uri, database_name):
    """Connect to a target MongoDB database."""

    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000,
    )

    client.admin.command("ping")

    logger.info(
        "Connected to database: %s",
        database_name,
    )

    return client, client[database_name]


# ============================================================
# GOOGLE SHEETS CONNECTION
# ============================================================

def connect_google_sheets():
    """Authenticate using the Google service account."""

    if not os.path.isfile(GOOGLE_CREDENTIALS):
        raise FileNotFoundError(
            f"Credentials file not found: {GOOGLE_CREDENTIALS}"
        )

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    google_client = gspread.authorize(credentials)

    spreadsheet = google_client.open_by_key(
        SPREADSHEET_ID
    )

    logger.info("Connected to Google Sheets.")

    return spreadsheet


# ============================================================
# READ EMPLOYER MAPPINGS
# ============================================================

def get_employers(spreadsheet):
    """
    Read employer mappings from Domains worksheet.

    Required columns:
        Client
        EmployerId
        jobicare employerId
    """

    worksheet = sheets_request(
        spreadsheet.worksheet,
        DOMAINS_SHEET,
    )

    records = sheets_request(
        worksheet.get_all_records
    )

    employers = []
    seen = set()

    for row in records:

        client_name = str(
            row.get("Client", "")
        ).strip()

        employer_id = str(
            row.get("EmployerId", "")
        ).strip()

        jobicare_employer_id = str(
            row.get("jobicare employerId", "")
        ).strip()

        if not client_name:
            continue

        if not employer_id or not jobicare_employer_id:

            logger.warning(
                "Skipping '%s': employer mapping incomplete.",
                client_name,
            )

            continue

        if len(client_name) > 100:

            logger.warning(
                "Skipping '%s': worksheet name exceeds 100 characters.",
                client_name,
            )

            continue

        employer_key = (
            client_name,
            employer_id,
            jobicare_employer_id,
        )

        if employer_key in seen:
            continue

        seen.add(employer_key)

        employers.append({
            "client": client_name,
            "employer_id": employer_id,
            "jobicare_employer_id": jobicare_employer_id,
        })

    logger.info(
        "Loaded %s employer mappings from '%s'.",
        len(employers),
        DOMAINS_SHEET,
    )

    return employers


# ============================================================
# QUERY 1: GET EXPIRED JOBICARE UNIQUE KEYS
# ============================================================

def get_expiry_unique_keys(
    jobicare_db,
    jobicare_employer_id,
):
    """
    Target:
        jobicarenode_prod.Target_P4_Opt

    Conditions:
        employerId = Jobicare employer ID
        job_status = 3
        gpost = 3

    Returns:
        Unique uniqueKey values.
    """

    collection = jobicare_db[
        JOBICARE_COLLECTION
    ]

    query = {
        "employerId": jobicare_employer_id,
        "job_status": 3,
        "gpost": 3,
    }

    projection = {
        "_id": 0,
        "uniqueKey": 1,
    }

    unique_keys = []

    cursor = collection.find(
        query,
        projection,
        batch_size=MONGO_BATCH_SIZE,
    )

    try:

        for document in cursor:

            unique_key = document.get("uniqueKey")

            if (
                isinstance(unique_key, str)
                and unique_key.strip()
            ):
                unique_keys.append(unique_key)

    finally:
        cursor.close()

    unique_keys = list(
        dict.fromkeys(unique_keys)
    )

    logger.info(
        "%s: found %s unique keys.",
        jobicare_employer_id,
        len(unique_keys),
    )

    return unique_keys


# ============================================================
# QUERY 2: GET MATCHING PRODUCTION JOBS
# ============================================================

def get_matching_jobs(
    prod_db,
    employer_id,
    unique_keys,
):
    """
    Target:
        prod_jobiak_ai.job

    Conditions:
        employerId = production employer ID
        status = posted
        isActive = true
        clientJobId in Jobicare uniqueKey values
    """

    if not unique_keys:
        return []

    collection = prod_db[
        PROD_COLLECTION
    ]

    projection = {
        "_id": 0,
        "clientJobId": 1,
        "isActive": 1,
        "status": 1,
        "jobId": 1,
        "title": 1,
        "datePosted": 1,
        "employerId": 1,
    }

    matching_jobs = []
    seen_client_job_ids = set()

    for start in range(
        0,
        len(unique_keys),
        MONGO_BATCH_SIZE,
    ):

        key_batch = unique_keys[
            start:start + MONGO_BATCH_SIZE
        ]

        query = {
            "employerId": employer_id,
            "status": "posted",
            "isActive": True,
            "clientJobId": {
                "$in": key_batch,
            },
        }

        cursor = collection.find(
            query,
            projection,
            batch_size=MONGO_BATCH_SIZE,
        )

        try:

            for document in cursor:

                client_job_id = document.get(
                    "clientJobId"
                )

                if client_job_id in seen_client_job_ids:
                    continue

                seen_client_job_ids.add(
                    client_job_id
                )

                matching_jobs.append(document)

        finally:
            cursor.close()

    logger.info(
        "%s: found %s matching active jobs.",
        employer_id,
        len(matching_jobs),
    )

    return matching_jobs


# ============================================================
# QUERY 3: GET INDIVIDUAL JOB VIEWS
# ============================================================

def get_job_views(
    prod_db,
    employer_id,
    jobs,
):
    """
    Calculate individual Google-origin views.

    Matching:
        userAnalytics.childJobId = job.jobId

    Filters:
        employerId = production employer ID
        isBot = false
        browserType != Unknown
        deviceType != Unknown
        isFromGoogle = true

    No date restriction is applied.
    """

    if not jobs:
        return {}

    job_ids = list({
        str(job.get("jobId"))
        for job in jobs
        if job.get("jobId") is not None
    })

    if not job_ids:
        return {}

    pipeline = [
        {
            "$match": {
                "employerId": employer_id,
                "isBot": False,
                "browserType": {
                    "$ne": "Unknown",
                },
                "deviceType": {
                    "$ne": "Unknown",
                },
                "isFromGoogle": True,
                "childJobId": {
                    "$in": job_ids,
                },
            }
        },
        {
            "$group": {
                "_id": "$childJobId",
                "jobViews": {
                    "$sum": 1,
                },
            }
        },
    ]

    results = prod_db[
        ANALYTICS_COLLECTION
    ].aggregate(
        pipeline,
        allowDiskUse=True,
    )

    views = {}

    for record in results:

        views[str(record["_id"])] = record["jobViews"]

    logger.info(
        "%s: calculated individual views for %s jobs.",
        employer_id,
        len(views),
    )

    return views


# ============================================================
# QUERY 4: GET TITLE VIEWS
# ============================================================

def get_title_views(
    prod_db,
    employer_id,
):
    """
    Calculate Google-origin views grouped by exact job title.

    Date range:
        September 1, 2026 to October 30, 2026 (exclusive).

    Analytics are joined to production jobs using:
        childJobId = jobId

    Results are grouped by:
        job.title
    """

    pipeline = [
        {
            "$match": {
                "employerId": employer_id,
                "isBot": False,
                "browserType": {
                    "$ne": "Unknown",
                },
                "deviceType": {
                    "$ne": "Unknown",
                },
                "isFromGoogle": True,
                "createdDt": {
                    "$gt": TITLE_VIEWS_START,
                    "$lt": TITLE_VIEWS_END,
                },
            }
        },
        {
            "$lookup": {
                "from": PROD_COLLECTION,
                "localField": "childJobId",
                "foreignField": "jobId",
                "as": "jobDetails",
            }
        },
        {
            "$unwind": "$jobDetails",
        },
        {
            "$match": {
                "jobDetails.employerId": employer_id,
                "jobDetails.title": {
                    "$exists": True,
                    "$nin": [None, ""],
                },
            }
        },
        {
            "$group": {
                "_id": "$jobDetails.title",
                "titleViews": {
                    "$sum": 1,
                },
            }
        },
    ]

    results = prod_db[
        ANALYTICS_COLLECTION
    ].aggregate(
        pipeline,
        allowDiskUse=True,
    )

    views = {}

    for record in results:

        views[record["_id"]] = record["titleViews"]

    logger.info(
        "%s: calculated title views for %s titles.",
        employer_id,
        len(views),
    )

    return views


# ============================================================
# FORMAT VALUES
# ============================================================

def format_value(value):
    """Convert MongoDB values into Sheets-compatible values."""

    if value is None:
        return ""

    if isinstance(value, datetime):

        return value.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    if isinstance(value, bool):
        return str(value).lower()

    if isinstance(value, (str, int, float)):
        return value

    return str(value)


# ============================================================
# PREPARE OUTPUT ROWS
# ============================================================

def prepare_output_rows(
    employer,
    jobs,
    checked_at,
    job_views,
    title_views,
):
    """Prepare output rows with individual and title-level views."""

    rows = []

    for job in jobs:

        job_id = job.get("jobId")
        title = job.get("title")

        individual_views = job_views.get(
            str(job_id),
            0,
        )

        title_view_count = title_views.get(
            title,
            0,
        )

        rows.append([
            employer["client"],
            employer["employer_id"],
            employer["jobicare_employer_id"],

            format_value(job_id),
            format_value(title),
            format_value(job.get("status")),
            format_value(job.get("isActive")),
            format_value(job.get("datePosted")),

            individual_views,
            title_view_count,

            checked_at,
        ])

    return rows


# ============================================================
# CHECKPOINT MANAGEMENT
# ============================================================

def load_checkpoint():
    """Load existing results to resume an interrupted execution."""

    if not CACHE_FILE.exists():

        logger.info(
            "No existing checkpoint found. Starting a new run."
        )

        return {
            "version": CACHE_VERSION,
            "checked_at": datetime.now(
                timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "clients": {},
        }

    try:

        with open(
            CACHE_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            checkpoint = json.load(file)

        if checkpoint.get("version") != CACHE_VERSION:

            logger.warning(
                "Checkpoint version mismatch. Starting a new run."
            )

            return {
                "version": CACHE_VERSION,
                "checked_at": datetime.now(
                    timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "clients": {},
            }

        logger.info(
            "Existing checkpoint found. Resuming previous run."
        )

        return checkpoint

    except (OSError, json.JSONDecodeError) as error:

        raise RuntimeError(
            f"Could not safely read checkpoint: {error}"
        ) from error


def save_checkpoint(checkpoint):
    """Save results atomically."""

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = CACHE_FILE.with_suffix(".tmp")

    with open(
        temporary_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            checkpoint,
            file,
            indent=2,
            ensure_ascii=False,
        )

    os.replace(
        temporary_file,
        CACHE_FILE,
    )


def clear_checkpoint():
    """Delete checkpoint after every client is successfully updated."""

    if CACHE_FILE.exists():

        CACHE_FILE.unlink()

        logger.info(
            "Checkpoint deleted after successful completion."
        )

    if CACHE_DIR.exists():

        try:
            CACHE_DIR.rmdir()
        except OSError:
            pass


# ============================================================
# GET OR CREATE CLIENT WORKSHEET
# ============================================================

def get_client_worksheet(
    spreadsheet,
    client_name,
):
    """Get the client worksheet or create it."""

    try:

        return sheets_request(
            spreadsheet.worksheet,
            client_name,
        )

    except gspread.WorksheetNotFound:

        logger.info(
            "Creating worksheet for client: %s",
            client_name,
        )

        return sheets_request(
            spreadsheet.add_worksheet,
            title=client_name,
            rows=1000,
            cols=len(OUTPUT_HEADERS),
        )


# ============================================================
# UPDATE CLIENT WORKSHEET
# ============================================================

def update_client_worksheet(
    spreadsheet,
    client_name,
    output_rows,
):
    """
    Refresh only the client's worksheet.

    Important:
        - Never reduce existing worksheet dimensions.
        - Preserve frozen rows.
        - Clear only the output columns.
        - Write all data in one update request.
    """

    worksheet = get_client_worksheet(
        spreadsheet,
        client_name,
    )

    values = [
        OUTPUT_HEADERS,
        *output_rows,
    ]

    required_rows = len(values)
    required_cols = len(OUTPUT_HEADERS)

    current_rows = worksheet.row_count
    current_cols = worksheet.col_count

    # Expand only when necessary.
    # Never shrink the worksheet.
    if (
        required_rows > current_rows
        or required_cols > current_cols
    ):

        sheets_request(
            worksheet.resize,
            rows=max(
                current_rows,
                required_rows,
            ),
            cols=max(
                current_cols,
                required_cols,
            ),
        )

    # Clear only the output columns.
    # This does not delete worksheet rows or frozen rows.
    sheets_request(
        worksheet.batch_clear,
        ["A:K"],
    )

    # Write header and data in one request.
    sheets_request(
        worksheet.update,
        range_name="A1",
        values=values,
        value_input_option="RAW",
    )

    logger.info(
        "Updated '%s': %s matching jobs.",
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
        logger.info("JOB EXPIRY CHECK STARTED")
        logger.info("=" * 65)

        # ----------------------------------------------------
        # 1. Load checkpoint.
        # ----------------------------------------------------

        checkpoint = load_checkpoint()

        checked_at = checkpoint["checked_at"]

        # ----------------------------------------------------
        # 2. Connect to MongoDB.
        # ----------------------------------------------------

        primary_client = connect_primary_mongodb()

        mongo_uris = get_mongo_uris(
            primary_client
        )

        jobicare_client, jobicare_db = connect_target_mongodb(
            mongo_uris[JOBICARE_DATABASE],
            JOBICARE_DATABASE,
        )

        prod_client, prod_db = connect_target_mongodb(
            mongo_uris[PROD_DATABASE],
            PROD_DATABASE,
        )

        # ----------------------------------------------------
        # 3. Connect to Google Sheets.
        # ----------------------------------------------------

        spreadsheet = connect_google_sheets()

        # ----------------------------------------------------
        # 4. Read employer mappings.
        # ----------------------------------------------------

        employers = get_employers(
            spreadsheet
        )

        if not employers:

            raise RuntimeError(
                "No valid employers found in Domains worksheet."
            )

        total_unique_keys = 0
        total_matching_jobs = 0
        total_job_views = 0

        # ----------------------------------------------------
        # 5. Process each client.
        # ----------------------------------------------------

        for employer in employers:

            client_name = employer["client"]

            employer_id = employer["employer_id"]

            jobicare_employer_id = employer[
                "jobicare_employer_id"
            ]

            cache_key = employer_id

            logger.info("-" * 65)

            logger.info(
                "Processing client: %s",
                client_name,
            )

            cached_client = checkpoint["clients"].get(
                cache_key
            )

            # ------------------------------------------------
            # CASE 1: Existing checkpoint.
            # ------------------------------------------------

            if (
                cached_client
                and cached_client.get("client") == client_name
                and cached_client.get("employer_id") == employer_id
                and cached_client.get("jobicare_employer_id")
                == jobicare_employer_id
            ):

                logger.info(
                    "%s: loading saved results. "
                    "Skipping all MongoDB queries.",
                    client_name,
                )

                output_rows = cached_client["output_rows"]

                unique_count = cached_client["unique_keys"]

                matching_count = cached_client["matching_jobs"]

            # ------------------------------------------------
            # CASE 2: Fetch fresh MongoDB results.
            # ------------------------------------------------

            else:

                logger.info(
                    "%s: fetching data from MongoDB.",
                    client_name,
                )

                # Query 1: Jobicare expired unique keys.
                unique_keys = get_expiry_unique_keys(
                    jobicare_db,
                    jobicare_employer_id,
                )

                unique_count = len(unique_keys)

                # Query 2: Production matching jobs.
                matching_jobs = get_matching_jobs(
                    prod_db,
                    employer_id,
                    unique_keys,
                )

                matching_count = len(matching_jobs)

                # Query 3: Individual job views.
                job_views = get_job_views(
                    prod_db,
                    employer_id,
                    matching_jobs,
                )

                # Query 4: Title views.
                title_views = get_title_views(
                    prod_db,
                    employer_id,
                )

                logger.info(
                    "%s | Job Views: %s",
                    client_name,
                    sum(job_views.values()),
                )

                logger.info(
                    "%s | Unique Titles with Views: %s",
                    client_name,
                    len(title_views),
                )

                # Prepare output.
                output_rows = prepare_output_rows(
                    employer,
                    matching_jobs,
                    checked_at,
                    job_views,
                    title_views,
                )

                # Save BEFORE updating Google Sheets.
                checkpoint["clients"][cache_key] = {
                    "client": client_name,
                    "employer_id": employer_id,
                    "jobicare_employer_id": jobicare_employer_id,
                    "unique_keys": unique_count,
                    "matching_jobs": matching_count,
                    "output_rows": output_rows,
                }

                save_checkpoint(checkpoint)

                logger.info(
                    "%s: MongoDB results saved to checkpoint.",
                    client_name,
                )

            total_unique_keys += unique_count

            total_matching_jobs += matching_count

            total_job_views += sum(
                row[8] if isinstance(row[8], (int, float)) else 0
                for row in output_rows
            )

            # ------------------------------------------------
            # 6. Update Google Sheets.
            # ------------------------------------------------

            update_client_worksheet(
                spreadsheet,
                client_name,
                output_rows,
            )

        # ----------------------------------------------------
        # 7. Final summary.
        # ----------------------------------------------------

        logger.info("=" * 65)
        logger.info("JOB EXPIRY CHECK COMPLETED")

        logger.info(
            "Employers processed: %s",
            len(employers),
        )

        logger.info(
            "Total expired unique keys: %s",
            total_unique_keys,
        )

        logger.info(
            "Total matching active jobs: %s",
            total_matching_jobs,
        )

        logger.info(
            "Total individual Job Views: %s",
            total_job_views,
        )

        logger.info("=" * 65)

        # Remove checkpoint only when all clients succeed.
        clear_checkpoint()

    except Exception:

        logger.exception(
            "JOB EXPIRY CHECK FAILED"
        )

        logger.warning(
            "Checkpoint retained. "
            "Restart the script to resume without repeating saved MongoDB queries."
        )

        raise

    finally:

        for client in (
            prod_client,
            jobicare_client,
            primary_client,
        ):

            if client is not None:
                client.close()

        logger.info(
            "MongoDB connections closed."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
