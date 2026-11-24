import os
import re
import logging
from collections import defaultdict
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

# Primary MongoDB connection: accesses mongo_creds.creds
MONGO_URI = os.getenv("MONGO_URI")

# Credentials collection
CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"

# JobiCare
JOBICARE_DATABASE = "data_cleansing"
JOBICARE_COLLECTION = "ETL_Job_Log"

# Keyword rules
PROD_DATABASE = "prod_jobiak_ai"
KEYWORD_COLLECTION = "jobiak_keyword_Updation"
EMPLOYER_ID = "6aa8d214060e8f0b78b0dc87"

# Scraping data. The collection name uses the same spelling as the
# collection specified in the workflow: ETL_Scrapping_Data.
SCRAPING_DATABASE = "ETL_Scrapping_Data"
SCRAPING_COLLECTION = "ETL_Scrapping_Data"
SCRAPING_MONGO_URI = os.getenv("SCRAPING_MONGO_URI")

# Google Sheets
GOOGLE_CREDENTIALS = "credentials.json"
SPREADSHEET_ID = "1y9cZZslDri14RBAefdwkYSrvbx5NurpZFEQ3MfM9moM"
WORKSHEET_NAME = "Postings"

MONGO_BATCH_SIZE = 500
MIN_WORKSHEET_ROWS = 100

OUTPUT_HEADERS = [
    "clientJobId",
    "JobiCare Job Title",
    "Normalized Job Title",
    "Location",
    "Grouped Title Count",
    "Keyword",
    "Keyword Title",
    "Keyword Type",
    "Operator Type",
    "Company Name",
    "Scraped Title",
    "Scraping Job Status",
    "Scraping Update Time",
    "Match Reason",
    "Checked At (UTC)",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# PRIMARY MONGODB CONNECTION AND CREDENTIAL LOOKUP
# ============================================================

def connect_primary_mongodb():
    """Connect using MONGO_URI from .env."""
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
    """Retrieve data_cleansing and production MongoDB URIs from mongo_creds.creds."""
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
        logger.info("Retrieved MongoDB URI for domain %s.", domain)

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
    if not os.path.isfile(GOOGLE_CREDENTIALS):
        raise FileNotFoundError(
            f"Google service-account credentials file not found: {GOOGLE_CREDENTIALS}. "
            "Place credentials.json in the script's working directory or update "
            "GOOGLE_CREDENTIALS."
        )

    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    google_client = gspread.authorize(credentials)
    spreadsheet = google_client.open_by_key(SPREADSHEET_ID)
    logger.info("Connected to Google Sheets.")
    return spreadsheet


def get_or_create_worksheet(spreadsheet):
    try:
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=WORKSHEET_NAME,
            rows=MIN_WORKSHEET_ROWS,
            cols=len(OUTPUT_HEADERS),
        )
    return worksheet


def write_report(spreadsheet, rows):
    """Refresh only the Postings worksheet; other tabs are untouched."""
    worksheet = get_or_create_worksheet(spreadsheet)
    values = [OUTPUT_HEADERS] + rows

    # Keep more than one visible row so freezing row 1 is valid even when
    # there are no output records. Do not shrink the worksheet to one row.
    required_rows = max(MIN_WORKSHEET_ROWS, len(values))
    worksheet.resize(rows=required_rows, cols=len(OUTPUT_HEADERS))
    worksheet.clear()
    worksheet.update(
        range_name="A1",
        values=values,
        value_input_option="RAW",
    )

    try:
        worksheet.freeze(rows=1)
    except gspread.exceptions.GSpreadException:
        # Formatting must not make a successfully written report fail.
        logger.exception("Could not freeze the header row.")

    last_column = chr(ord("A") + len(OUTPUT_HEADERS) - 1)
    worksheet.format(
        f"A1:{last_column}1",
        {
            "textFormat": {"bold": True},
            "wrapStrategy": "WRAP",
        },
    )

    logger.info(
        "Updated worksheet '%s' with %s records.",
        WORKSHEET_NAME,
        len(rows),
    )


# ============================================================
# TITLE NORMALIZATION
# ============================================================

def normalize_title(value):
    """Lowercase a title and replace punctuation with single spaces."""
    if value is None:
        return ""
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


# ============================================================
# STEP 1: GROUP ALL JOBICARE JOB TITLES
# ============================================================

def get_grouped_job_titles(jobicare_db):
    """Group all jobtitle values in data_cleansing.ETL_Job_Log.

    Uses MongoDB conversion to avoid aggregation errors if jobtitle has a
    non-string value. Python normalization merges punctuation variants too.
    Diagnostics are logged to help identify a wrong collection or field.
    """
    collection = jobicare_db[JOBICARE_COLLECTION]

    try:
        document_count = collection.count_documents({})
        title_field_count = collection.count_documents(
            {"jobtitle": {"$exists": True, "$nin": [None, ""]}}
        )
        logger.info("JobiCare/source database: %s", jobicare_db.name)
        logger.info("Collections in source database %s: %s", jobicare_db.name, jobicare_db.list_collection_names())
        logger.info("Collection '%s' document count: %s", JOBICARE_COLLECTION, document_count)
        logger.info("Documents with a non-empty jobtitle field: %s", title_field_count)

        if document_count == 0:
            sample_collections = jobicare_db.list_collection_names()
            raise RuntimeError(
                f"Collection {jobicare_db.name}.{JOBICARE_COLLECTION} is empty or is not "
                f"the expected collection. Available collections: {sample_collections}. "
                "Verify JOBICARE_COLLECTION before continuing."
            )

        sample = collection.find_one({}, {"_id": 0, "jobtitle": 1, "uniqueKey": 1})
        if sample:
            # Do not log complete records or connection details.
            logger.info("Sample JobiCare title fields: %s", sample)

        if title_field_count == 0:
            sample_full = collection.find_one({}, {"_id": 0}) or {}
            sample_keys = list(sample_full.keys())
            raise RuntimeError(
                f"Collection {jobicare_db.name}.{JOBICARE_COLLECTION} contains documents, "
                "but none have a non-empty 'jobtitle' field. "
                f"Sample document field names: {sample_keys}. "
                "Update JOBICARE_COLLECTION or the title field name to match the schema."
            )

        pipeline = [
            {
                "$match": {
                    "jobtitle": {"$exists": True, "$nin": [None, ""]}
                }
            },
            {
                "$project": {
                    "safeTitle": {
                        "$convert": {
                            "input": "$jobtitle",
                            "to": "string",
                            "onError": "",
                            "onNull": "",
                        }
                    }
                }
            },
            {"$match": {"safeTitle": {"$ne": ""}}},
            {
                "$group": {
                    "_id": {
                        "$toLower": {
                            "$trim": {"input": "$safeTitle"}
                        }
                    },
                    "jobCount": {"$sum": 1},
                    "originalTitles": {"$addToSet": "$safeTitle"},
                }
            },
        ]

        # Merge aggregation groups that differ only by punctuation after
        # normalize_title(), and sum their counts rather than overwriting them.
        grouped_titles = {}
        for document in collection.aggregate(pipeline, allowDiskUse=True):
            normalized = normalize_title(document.get("_id"))
            if not normalized:
                continue

            if normalized not in grouped_titles:
                grouped_titles[normalized] = {
                    "count": 0,
                    "original_titles": [],
                }

            grouped_titles[normalized]["count"] += int(document.get("jobCount", 0))
            existing = set(grouped_titles[normalized]["original_titles"])
            for title in document.get("originalTitles", []):
                title_text = str(title).strip()
                if title_text and title_text not in existing:
                    grouped_titles[normalized]["original_titles"].append(title_text)
                    existing.add(title_text)

        logger.info(
            "Grouped %s distinct normalized JobiCare titles from %s documents with titles.",
            len(grouped_titles),
            title_field_count,
        )
        if not grouped_titles:
            raise RuntimeError(
                "JobiCare documents contain jobtitle values, but normalization produced no "
                "titles. Check the title data and aggregation pipeline."
            )
        return grouped_titles

    except PyMongoError:
        logger.exception("MongoDB error while grouping JobiCare titles.")
        raise


# ============================================================
# STEP 2: FETCH ACTIVE KEYWORD RECORDS
# ============================================================

def get_active_keywords(prod_db):
    """Fetch active keyword rules for the configured employer."""
    collection = prod_db[KEYWORD_COLLECTION]
    query = {
        "employerId": EMPLOYER_ID,
        "isActive": True,
        "title": {"$exists": True, "$nin": ["", None]},
        "keyword": {"$exists": True, "$nin": ["", None]},
    }
    projection = {
        "_id": 0,
        "keyword": 1,
        "keywordType": 1,
        "operatorType": 1,
        "title": 1,
        "isActive": 1,
        "companyName": 1,
    }
    keywords = list(collection.find(query, projection))
    logger.info(
        "Fetched %s active keyword records for employer %s.",
        len(keywords),
        EMPLOYER_ID,
    )
    return keywords


# ============================================================
# STEP 3: MATCH KEYWORD TITLES TO GROUPED TITLES
# ============================================================

def title_matches(job_title, keyword_title, operator_type):
    """Apply contains-title or equals-title matching, case-insensitively."""
    job_normalized = normalize_title(job_title)
    keyword_normalized = normalize_title(keyword_title)
    if not job_normalized or not keyword_normalized:
        return False

    operator = str(operator_type or "").strip().lower()
    if operator == "contains-title":
        return re.search(
            r"\b" + re.escape(keyword_normalized) + r"\b",
            job_normalized,
        ) is not None
    if operator == "equals-title":
        return job_normalized == keyword_normalized
    return False


def match_grouped_titles(grouped_titles, keywords):
    """Match normalized JobiCare titles to active keyword rules."""
    matched_titles = defaultdict(list)

    for normalized_job_title, title_info in grouped_titles.items():
        for original_title in title_info["original_titles"]:
            for keyword in keywords:
                if title_matches(
                    original_title,
                    keyword.get("title"),
                    keyword.get("operatorType"),
                ):
                    matched_titles[normalized_job_title].append(keyword)

    # Deduplicate keyword rules for each normalized JobiCare title.
    deduplicated = {}
    for normalized_title, rules in matched_titles.items():
        unique_rules = {}
        for keyword in rules:
            key = (
                keyword.get("keyword"),
                keyword.get("title"),
                keyword.get("operatorType"),
            )
            unique_rules[key] = keyword
        if unique_rules:
            deduplicated[normalized_title] = list(unique_rules.values())

    logger.info("%s grouped titles matched active keyword rules.", len(deduplicated))
    return deduplicated


# ============================================================
# STEP 4: QUERY JOBICARE USING MATCHED TITLES
# ============================================================

def get_matching_jobicare_records(jobicare_db, grouped_titles, matched_titles):
    """Fetch JobiCare records whose normalized titles matched active rules."""
    if not matched_titles:
        logger.warning(
            "No JobiCare titles matched active keyword rules. Skipping the JobiCare record query."
        )
        return []

    normalized_titles = list(matched_titles.keys())
    collection = jobicare_db[JOBICARE_COLLECTION]

    # Convert title values to strings safely before normalizing in MongoDB.
    query = {
        "$expr": {
            "$in": [
                {
                    "$toLower": {
                        "$trim": {
                            "input": {
                                "$convert": {
                                    "input": "$jobtitle",
                                    "to": "string",
                                    "onError": "",
                                    "onNull": "",
                                }
                            }
                        }
                    }
                },
                # The Python normalizer removes punctuation, so matching on
                # raw lower/trim values alone would miss punctuation variants.
                # Query records in batches below using the title strings.
                normalized_titles,
            ]
        }
    }

    projection = {
        "_id": 0,
        "uniqueKey": 1,
        "jobtitle": 1,
        "location": 1,
        "job_status": 1,
        "gpost": 1,
    }

    # Use a safe projection scan because Mongo's simple lower/trim expression
    # does not remove punctuation in the same way as normalize_title().
    # Only title and required output fields are returned from MongoDB.
    cursor = collection.find(
        {"jobtitle": {"$exists": True, "$nin": [None, ""]}},
        projection,
        batch_size=MONGO_BATCH_SIZE,
    )
    records = []
    try:
        for record in cursor:
            normalized = normalize_title(record.get("jobtitle"))
            if normalized in matched_titles:
                records.append(record)
    finally:
        cursor.close()

    # Keep distinct job records. A clientJobId can occasionally appear with
    # multiple titles or locations, so don't discard those variants.
    unique_records = {}
    for record in records:
        unique_key = record.get("uniqueKey")
        if unique_key is None or not str(unique_key).strip():
            continue
        key = (
            str(unique_key),
            normalize_title(record.get("jobtitle")),
            str(record.get("location") or "").strip(),
        )
        unique_records[key] = record

    result = list(unique_records.values())
    logger.info("Found %s unique JobiCare records for matched titles.", len(result))
    return result


# ============================================================
# STEP 5: FIND SCRAPING RECORDS BY CLIENTJOBID
# ============================================================

def get_scraping_records(scraping_db, jobicare_records):
    """Match JobiCare uniqueKey values to ETL_Scrapping_Data.clientJobId.

    When several scraping records exist for a clientJobId, keep the record
    with the latest updatetime.
    """
    client_job_ids = list({
        str(record["uniqueKey"])
        for record in jobicare_records
        if record.get("uniqueKey") is not None
    })
    if not client_job_ids:
        return {}

    collection = scraping_db[SCRAPING_COLLECTION]
    scraping_records = {}

    for start in range(0, len(client_job_ids), MONGO_BATCH_SIZE):
        batch = client_job_ids[start:start + MONGO_BATCH_SIZE]
        query = {"clientJobId": {"$in": batch}}
        projection = {
            "_id": 0,
            "clientJobId": 1,
            "title": 1,
            "updatetime": 1,
            "job_status": 1,
        }
        cursor = collection.find(
            query,
            projection,
            batch_size=MONGO_BATCH_SIZE,
        ).sort("updatetime", -1)
        try:
            for record in cursor:
                client_job_id = record.get("clientJobId")
                if client_job_id is None:
                    continue
                key = str(client_job_id)
                # Cursor is sorted newest first, so keep the first per ID.
                if key not in scraping_records:
                    scraping_records[key] = record
        finally:
            cursor.close()

    logger.info(
        "Found scraping records for %s clientJobId values.",
        len(scraping_records),
    )
    return scraping_records


# ============================================================
# STEP 6: FORMAT VALUES
# ============================================================

def format_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return value
    return str(value)


# ============================================================
# STEP 7: PREPARE POSTING CANDIDATES
# ============================================================

def prepare_output_rows(jobicare_records, grouped_titles, matched_titles, scraping_records):
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rows = []

    for job in jobicare_records:
        unique_key = job.get("uniqueKey")
        if unique_key is None:
            continue

        client_job_id = str(unique_key)
        job_title = job.get("jobtitle", "")
        normalized = normalize_title(job_title)
        scraped = scraping_records.get(client_job_id)
        if not scraped:
            continue

        matching_keywords = matched_titles.get(normalized, [])
        for keyword in matching_keywords:
            keyword_title = keyword.get("title", "")
            operator_type = keyword.get("operatorType", "")
            scraped_title = scraped.get("title", "")

            # Both the JobiCare title and scraped title must satisfy the rule.
            if not title_matches(scraped_title, keyword_title, operator_type):
                continue

            rows.append([
                client_job_id,
                format_value(job_title),
                normalized,
                format_value(job.get("location")),
                grouped_titles.get(normalized, {}).get("count", 0),
                format_value(keyword.get("keyword")),
                format_value(keyword_title),
                format_value(keyword.get("keywordType")),
                format_value(operator_type),
                format_value(keyword.get("companyName")),
                format_value(scraped_title),
                format_value(scraped.get("job_status")),
                format_value(scraped.get("updatetime")),
                f"JobiCare and scraped titles match {operator_type}",
                checked_at,
            ])

    unique_rows = []
    seen = set()
    for row in rows:
        key = (row[0], row[5], row[6], row[8])
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)

    logger.info("Prepared %s eligible posting rows.", len(unique_rows))
    return unique_rows


# ============================================================
# MAIN
# ============================================================

def main():
    primary_client = None
    jobicare_client = None
    prod_client = None
    scraping_client = None

    try:
        logger.info("=" * 60)
        logger.info("POSTING CANDIDATE CHECK STARTED")
        logger.info("=" * 60)

        # 1. Connect to the primary MongoDB and retrieve saved URIs.
        primary_client = connect_primary_mongodb()
        mongo_uris = get_mongo_uris(primary_client)

        # 2. Connect to JobiCare and the keyword database.
        jobicare_client, jobicare_db = connect_target_mongodb(
            mongo_uris[JOBICARE_DATABASE], JOBICARE_DATABASE
        )
        prod_client, prod_db = connect_target_mongodb(
            mongo_uris[PROD_DATABASE], PROD_DATABASE
        )

        # 3. Scraping data uses the JobiCare URI by default; allow an override.
        scraping_uri = SCRAPING_MONGO_URI or mongo_uris[JOBICARE_DATABASE]
        if scraping_uri == mongo_uris[JOBICARE_DATABASE]:
            scraping_client = jobicare_client
            scraping_db = scraping_client[SCRAPING_DATABASE]
        elif scraping_uri == mongo_uris[PROD_DATABASE]:
            scraping_client = prod_client
            scraping_db = scraping_client[SCRAPING_DATABASE]
        else:
            scraping_client, scraping_db = connect_target_mongodb(
                scraping_uri, SCRAPING_DATABASE
            )

        # 4. Connect to Google Sheets.
        spreadsheet = connect_google_sheets()

        # 5. Group titles, fetch keyword rules, and match titles.
        grouped_titles = get_grouped_job_titles(jobicare_db)
        keywords = get_active_keywords(prod_db)
        matched_titles = match_grouped_titles(grouped_titles, keywords)

        # 6. Get matching JobiCare records and join to scraping data.
        jobicare_records = get_matching_jobicare_records(
            jobicare_db, grouped_titles, matched_titles
        )
        scraping_records = get_scraping_records(scraping_db, jobicare_records)
        output_rows = prepare_output_rows(
            jobicare_records,
            grouped_titles,
            matched_titles,
            scraping_records,
        )

        # 7. Write report, even if it only contains the header row.
        write_report(spreadsheet, output_rows)

        logger.info("=" * 60)
        logger.info("POSTING CANDIDATE CHECK COMPLETED")
        logger.info("Grouped JobiCare titles: %s", len(grouped_titles))
        logger.info("Active keyword rules: %s", len(keywords))
        logger.info("Matched titles: %s", len(matched_titles))
        logger.info("JobiCare records: %s", len(jobicare_records))
        logger.info("Scraping records: %s", len(scraping_records))
        logger.info("Final posting rows: %s", len(output_rows))
        logger.info("=" * 60)

    except Exception:
        logger.exception("POSTING CANDIDATE CHECK FAILED")
        raise

    finally:
        # Close each distinct MongoClient only once.
        clients = {
            id(client): client
            for client in (
                scraping_client,
                prod_client,
                jobicare_client,
                primary_client,
            )
            if client is not None
        }
        for client in clients.values():
            client.close()
        logger.info("MongoDB connections closed.")


if __name__ == "__main__":
    main()
