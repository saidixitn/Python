"""
Tarun - Monthly Unique Views Report
===================================

Creates/refreshes ONLY the "Tarun monthly stats" Google Sheets tab.

Input:
  Spreadsheet -> Domains worksheet
  Columns A-D: Lead, Domain, Domain Type, EmployerId

MongoDB:
  Proxy      -> prod_jobiak_ai.userAnalytics
  DirectApply-> directclients_prod.userAnalytics
                directclients_prod.userAnalytics_old

Counting rule:
  One unique click per UTC date + IP + Job ID.
  Same IP + two different Job IDs on the same day = 2 clicks.

Direct Apply monthly columns:
  - userAnalytics Views
  - userAnalytics_old Views
  - Combined Unique Views (deduplicated across both collections)

No daily report, no summary report, no MongoDB writes, no CSV/Excel export.
"""

import os
import time
import logging
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import gspread
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing from your .env file.")

SPREADSHEET_ID = "1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds"
INPUT_WORKSHEET = "Domains"
OUTPUT_WORKSHEET = "Tarun monthly stats"

TARGET_LEAD = "tarun"
MAX_WORKERS = 30

# Update these lists if your MongoDB documents use different field names.
IP_FIELDS = ["ip", "ipAddress", "clientIp", "remoteAddress"]
JOB_ID_FIELDS = ["jobId", "job_id", "jobPubJobId", "jobPostingId"]

# Both analytics collections are currently queried using createdDt.
# If userAnalytics_old uses a different timestamp field in your DB,
# change OLD_DATE_FIELD to that exact field name.
CURRENT_DATE_FIELD = "createdDt"
OLD_DATE_FIELD = "createdDt"

# This is the same eligibility filter used in the previous report.
COMMON_FILTER = {
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True,
}

# Set to None to let MongoDB choose the index automatically.
# If you know the index exists, you can set this to "employerId_1".
INDEX_HINT = None

HEADER_BG = {"red": 0.12, "green": 0.20, "blue": 0.32}
SECTION_BG = {"red": 0.18, "green": 0.33, "blue": 0.59}
WHITE = {"red": 1, "green": 1, "blue": 1}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(threadName)s | %(message)s",
)
logger = logging.getLogger("TarunMonthlyStats")
SHEET_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# MONGODB CONNECTIONS
# ---------------------------------------------------------------------------

ROOT_CLIENT = MongoClient(MONGO_URI, maxPoolSize=MAX_WORKERS + 10)
CREDS_COLLECTION = ROOT_CLIENT["mongo_creds"]["creds"]

PROD_CRED = CREDS_COLLECTION.find_one({"domain": "prod_jobiak_ai"})
DC_CRED = CREDS_COLLECTION.find_one({"domain": "directclients_prod"})


def get_credential_uri(document, label):
    if not document:
        raise RuntimeError(f"Could not find MongoDB credentials for {label}.")

    uri = document.get("mongo_uri") or document.get("uri")
    if not uri:
        raise RuntimeError(f"MongoDB URI is missing for {label}.")

    return uri


PROD_CLIENT = MongoClient(
    get_credential_uri(PROD_CRED, "prod_jobiak_ai"),
    maxPoolSize=MAX_WORKERS + 10,
)
DC_CLIENT = MongoClient(
    get_credential_uri(DC_CRED, "directclients_prod"),
    maxPoolSize=MAX_WORKERS + 10,
)

PROD_DB = PROD_CLIENT["prod_jobiak_ai"]
DC_DB = DC_CLIENT["directclients_prod"]


# ---------------------------------------------------------------------------
# GOOGLE SHEETS INPUT
# ---------------------------------------------------------------------------

def open_spreadsheet():
    gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(SPREADSHEET_ID)


def read_tarun_domains(spreadsheet):
    worksheet = spreadsheet.worksheet(INPUT_WORKSHEET)
    rows = worksheet.get_all_values()

    domains = []
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) < 4:
            continue

        lead, domain, domain_type, employer_id = [
            str(value).strip() for value in row[:4]
        ]

        if not all([lead, domain, domain_type, employer_id]):
            continue

        if lead.casefold() == TARGET_LEAD:
            domains.append({
                "lead": lead,
                "domain": domain,
                "domain_type": domain_type,
                "employerId": employer_id,
                "source_row": row_number,
            })

    if not domains:
        raise RuntimeError(
            "No rows for Lead='Tarun' were found in the Domains worksheet."
        )

    logger.info("Found %d Tarun domain rows.", len(domains))
    return domains


# ---------------------------------------------------------------------------
# MONGODB AGGREGATION HELPERS
# ---------------------------------------------------------------------------

def first_available_field(field_names):
    """Return a Mongo expression selecting the first non-null field."""
    expression = None
    for field_name in reversed(field_names):
        value = f"${field_name}"
        if expression is None:
            expression = value
        else:
            expression = {"$ifNull": [value, expression]}
    return expression


IP_EXPRESSION = first_available_field(IP_FIELDS)
JOB_ID_EXPRESSION = first_available_field(JOB_ID_FIELDS)


def build_match(employer_id, date_field):
    match = dict(COMMON_FILTER)
    match["employerId"] = employer_id
    match[date_field] = {"$type": "date"}
    return {"$match": match}


def source_projection(employer_id, source_name, date_field):
    return [
        build_match(employer_id, date_field),
        {
            "$project": {
                "_id": 0,
                "day": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": f"${date_field}",
                        "timezone": "UTC",
                    }
                },
                "ip": IP_EXPRESSION,
                "jobId": JOB_ID_EXPRESSION,
                "source": {"$literal": source_name},
            }
        },
        {
            "$match": {
                "ip": {"$nin": [None, ""]},
                "jobId": {"$nin": [None, ""]},
            }
        },
    ]


def aggregate_with_optional_hint(collection, pipeline):
    options = {"allowDiskUse": True, "batchSize": 5000}

    if INDEX_HINT:
        options["hint"] = INDEX_HINT

    try:
        return list(collection.aggregate(pipeline, **options))
    except OperationFailure as exc:
        # If a configured hint is invalid, retry once without it.
        if INDEX_HINT and "hint" in str(exc).lower():
            logger.warning(
                "Index hint %s failed for %s; retrying without hint.",
                INDEX_HINT,
                collection.name,
            )
            options.pop("hint", None)
            return list(collection.aggregate(pipeline, **options))
        raise


def direct_apply_monthly(employer_id):
    """
    Monthly source counts and combined unique counts for Direct Apply.

    The grouping order is important:
      1. Deduplicate by UTC day + IP + Job ID.
      2. Count the unique keys by month.

    If the same key exists in both collections:
      - it contributes 1 to each source's own count;
      - it contributes only 1 to Combined Unique Views.
    """

    pipeline = source_projection(
        employer_id, "userAnalytics", CURRENT_DATE_FIELD
    )

    pipeline.append({
        "$unionWith": {
            "coll": "userAnalytics_old",
            "pipeline": source_projection(
                employer_id, "userAnalytics_old", OLD_DATE_FIELD
            ),
        }
    })

    pipeline.extend([
        {
            "$group": {
                "_id": {
                    "day": "$day",
                    "ip": "$ip",
                    "jobId": "$jobId",
                },
                "current_flag": {
                    "$max": {
                        "$cond": [
                            {"$eq": ["$source", "userAnalytics"]},
                            1,
                            0,
                        ]
                    }
                },
                "old_flag": {
                    "$max": {
                        "$cond": [
                            {"$eq": ["$source", "userAnalytics_old"]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {
            "$group": {
                "_id": {
                    "$substr": ["$_id.day", 0, 7]
                },
                "userAnalytics": {"$sum": "$current_flag"},
                "userAnalytics_old": {"$sum": "$old_flag"},
                "combined": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ])

    results = aggregate_with_optional_hint(
        DC_DB["userAnalytics"], pipeline
    )

    monthly = {
        row["_id"]: {
            "userAnalytics": int(row.get("userAnalytics", 0)),
            "userAnalytics_old": int(row.get("userAnalytics_old", 0)),
            "combined": int(row.get("combined", 0)),
        }
        for row in results
        if row.get("_id")
    }

    # Diagnostic: count documents passing the common filter in each source.
    # These are raw matching documents, not unique clicks.
    current_raw = DC_DB["userAnalytics"].count_documents(
        build_match(employer_id, CURRENT_DATE_FIELD)["$match"]
    )
    old_raw = DC_DB["userAnalytics_old"].count_documents(
        build_match(employer_id, OLD_DATE_FIELD)["$match"]
    )

    logger.info(
        "Direct Apply | employerId=%s | current raw docs=%s | old raw docs=%s "
        "| current unique=%s | old unique=%s | combined unique=%s",
        employer_id,
        current_raw,
        old_raw,
        sum(v["userAnalytics"] for v in monthly.values()),
        sum(v["userAnalytics_old"] for v in monthly.values()),
        sum(v["combined"] for v in monthly.values()),
    )

    if old_raw == 0:
        logger.warning(
            "No userAnalytics_old documents matched employerId=%s with "
            "the current filter and date field '%s'. Check employerId, "
            "filter fields, and OLD_DATE_FIELD.",
            employer_id,
            OLD_DATE_FIELD,
        )

    return monthly


def proxy_monthly(employer_id):
    """Proxy domains use prod_jobiak_ai.userAnalytics only."""

    pipeline = source_projection(
        employer_id, "userAnalytics", CURRENT_DATE_FIELD
    )

    pipeline.extend([
        {
            "$group": {
                "_id": {
                    "day": "$day",
                    "ip": "$ip",
                    "jobId": "$jobId",
                }
            }
        },
        {
            "$group": {
                "_id": {"$substr": ["$_id.day", 0, 7]},
                "userAnalytics": {"$sum": 1},
                "userAnalytics_old": {"$sum": 0},
                "combined": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ])

    results = aggregate_with_optional_hint(
        PROD_DB["userAnalytics"], pipeline
    )

    return {
        row["_id"]: {
            "userAnalytics": int(row.get("userAnalytics", 0)),
            "userAnalytics_old": 0,
            "combined": int(row.get("combined", 0)),
        }
        for row in results
        if row.get("_id")
    }


def process_domain(item):
    started = time.time()
    domain_type = item["domain_type"].strip().casefold()

    if domain_type == "proxy":
        monthly = proxy_monthly(item["employerId"])
    else:
        monthly = direct_apply_monthly(item["employerId"])

    logger.info(
        "Completed | %s | %s | %d months | %.1fs",
        item["domain"],
        item["employerId"],
        len(monthly),
        time.time() - started,
    )

    return item, monthly


# ---------------------------------------------------------------------------
# BUILD MONTHLY-ONLY OUTPUT
# ---------------------------------------------------------------------------

def build_monthly_rows(domains, monthly_by_row):
    rows = []

    for item in domains:
        monthly = monthly_by_row.get(item["source_row"], {})

        for year_month, counts in sorted(monthly.items()):
            year, month = year_month.split("-")

            rows.append([
                item["lead"],
                item["domain"],
                item["domain_type"],
                item["employerId"],
                int(year),
                int(month),
                year_month,
                counts["userAnalytics"],
                counts["userAnalytics_old"],
                counts["combined"],
            ])

    rows.sort(key=lambda row: (row[1].casefold(), row[6]))
    return rows


# ---------------------------------------------------------------------------
# GOOGLE SHEETS OUTPUT
# ---------------------------------------------------------------------------

def get_or_create_output_tab(spreadsheet, required_rows, required_cols):
    try:
        worksheet = spreadsheet.worksheet(OUTPUT_WORKSHEET)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=OUTPUT_WORKSHEET,
            rows=max(required_rows, 100),
            cols=max(required_cols, 10),
        )

    if worksheet.row_count < required_rows:
        worksheet.add_rows(required_rows - worksheet.row_count)

    if worksheet.col_count < required_cols:
        worksheet.add_cols(required_cols - worksheet.col_count)

    return worksheet


def publish_monthly_only(spreadsheet, monthly_rows):
    headers = [
        "Lead",
        "Domain",
        "Domain Type",
        "EmployerId",
        "Year",
        "Month",
        "Year-Month",
        "userAnalytics Views",
        "userAnalytics_old Views",
        "Combined Unique Views",
    ]

    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    values = [
        ["TARUN - MONTHLY UNIQUE VIEWS"],
        [f"Generated: {generated_at}"],
        ["Counting rule: one unique click per UTC date + IP + Job ID."],
        ["Same IP + two different Job IDs on the same day = 2 clicks."],
        ["Combined Unique Views deduplicates the same date + IP + Job ID across both Direct Apply collections."],
        [],
        headers,
    ]
    values.extend(monthly_rows)

    with SHEET_LOCK:
        worksheet = get_or_create_output_tab(
            spreadsheet,
            required_rows=len(values) + 5,
            required_cols=len(headers),
        )

        worksheet.clear()
        worksheet.update(
            range_name="A1",
            values=values,
            value_input_option="USER_ENTERED",
        )

        spreadsheet.batch_update({
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(headers),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": HEADER_BG,
                                "textFormat": {
                                    "bold": True,
                                    "fontSize": 14,
                                    "foregroundColor": WHITE,
                                },
                            }
                        },
                        "fields": "userEnteredFormat",
                    }
                },
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": worksheet.id,
                            "startRowIndex": 6,
                            "endRowIndex": 7,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(headers),
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": SECTION_BG,
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": WHITE,
                                },
                                "wrapStrategy": "WRAP",
                            }
                        },
                        "fields": "userEnteredFormat",
                    }
                },
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": worksheet.id,
                            "gridProperties": {
                                "frozenRowCount": 7,
                            },
                        },
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
            ]
        })

    logger.info(
        "Updated '%s' with %d monthly rows.",
        OUTPUT_WORKSHEET,
        len(monthly_rows),
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    started = time.time()
    spreadsheet = open_spreadsheet()
    domains = read_tarun_domains(spreadsheet)

    monthly_by_row = {}

    logger.info(
        "Starting Tarun monthly-only report: %d domains, %d workers.",
        len(domains),
        MAX_WORKERS,
    )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_domain, item): item
            for item in domains
        }

        completed = 0
        for future in as_completed(futures):
            item = futures[future]
            try:
                returned_item, monthly = future.result()
                monthly_by_row[returned_item["source_row"]] = monthly
            except Exception:
                logger.exception(
                    "Failed domain: %s | employerId=%s",
                    item["domain"],
                    item["employerId"],
                )
                monthly_by_row[item["source_row"]] = {}

            completed += 1
            logger.info("Progress: %d/%d", completed, len(domains))

    monthly_rows = build_monthly_rows(domains, monthly_by_row)
    publish_monthly_only(spreadsheet, monthly_rows)

    logger.info(
        "Finished | domains=%d | monthly rows=%d | elapsed=%.1fs",
        len(domains),
        len(monthly_rows),
        time.time() - started,
    )
    print(
        f"Completed. Monthly-only results are in the "
        f"'{OUTPUT_WORKSHEET}' worksheet."
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        for client in (PROD_CLIENT, DC_CLIENT, ROOT_CLIENT):
            try:
                client.close()
            except Exception:
                pass
