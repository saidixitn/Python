"""
Google Sheets -> MongoDB Analytics -> Google Sheets Report
===========================================================

INPUT:
  Google spreadsheet -> "Domains" worksheet
  Columns:
    A: Lead
    B: Domain
    C: Domain Type
    D: EmployerId

MONGODB SOURCES:
  Direct Apply:
    directclients_prod.userAnalytics
    directclients_prod.userAnalytics_prod
    Daily views from both collections are ADDED together.

  Proxy:
    prod_jobiak_ai.userAnalytics

OUTPUT:
  Writes one report worksheet per Lead into the SAME Google spreadsheet.
  Each Lead worksheet contains:
    1. Domain performance summary
    2. Monthly views

This script:
  - Does NOT create an Excel file or CSV.
  - Does NOT read or write daily_stats.
  - Does NOT write to MongoDB.
  - Does NOT modify the "Domains" input worksheet.
"""

import os
import time
import logging
import threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import gspread
from dotenv import load_dotenv
from pymongo import MongoClient


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found. Add it to your .env file.")

SPREADSHEET_ID = "1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds"
INPUT_WORKSHEET = "Domains"
TARGET_LEAD = "Hari Prasad"

# Yesterday is calculated automatically using UTC.
YESTERDAY_STR = (
    datetime.now(timezone.utc) - timedelta(days=1)
).strftime("%Y-%m-%d")

DC_WORKERS = 5
PROXY_WORKERS = 4

# Google Sheets worksheet formatting colors.
NAVY = {"red": 0.12, "green": 0.31, "blue": 0.47}
BLUE = {"red": 0.18, "green": 0.33, "blue": 0.59}
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("GoogleSheetDomainReport")

GSHEET_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# MONGODB CONNECTIONS
# ---------------------------------------------------------------------------

ROOT_CLIENT = MongoClient(MONGO_URI, maxPoolSize=50)
CREDS_COL = ROOT_CLIENT["mongo_creds"]["creds"]


def get_mongo_uri(credential_doc, credential_name):
    if not credential_doc:
        raise ValueError(
            f"MongoDB credentials not found for '{credential_name}'."
        )

    uri = credential_doc.get("mongo_uri") or credential_doc.get("uri")
    if not uri:
        raise ValueError(
            f"MongoDB URI missing for '{credential_name}'."
        )
    return uri


PROD_CRED = CREDS_COL.find_one({"domain": "prod_jobiak_ai"})
DC_CRED = CREDS_COL.find_one({"domain": "directclients_prod"})

PROD_CLIENT = MongoClient(
    get_mongo_uri(PROD_CRED, "prod_jobiak_ai"),
    maxPoolSize=30,
)
DC_CLIENT = MongoClient(
    get_mongo_uri(DC_CRED, "directclients_prod"),
    maxPoolSize=30,
)

PROD_DB = PROD_CLIENT["prod_jobiak_ai"]
DC_DB = DC_CLIENT["directclients_prod"]


# ---------------------------------------------------------------------------
# GOOGLE SHEETS CONNECTION + INPUT
# ---------------------------------------------------------------------------

def connect_google_sheets():
    gc = gspread.service_account(filename="credentials.json")
    return gc.open_by_key(SPREADSHEET_ID)


def fetch_domains_from_sheet(spreadsheet):
    """
    Reads client/domain records from the Domains worksheet.

    Expected columns:
      A = Lead
      B = Domain
      C = Domain Type
      D = EmployerId
    """
    worksheet = spreadsheet.worksheet(INPUT_WORKSHEET)
    rows = worksheet.get_all_values()

    if not rows or len(rows) < 2:
        raise ValueError(
            f"No client records found in '{INPUT_WORKSHEET}'."
        )

    domains = []

    for row_number, row in enumerate(rows[1:], start=2):
        if not any(str(value).strip() for value in row):
            continue

        if len(row) < 4:
            logger.warning(
                "Skipping row %s: expected 4 columns.", row_number
            )
            continue

        lead, domain, domain_type, employer_id = [
            str(value).strip() for value in row[:4]
        ]

        if not all([lead, domain, domain_type, employer_id]):
            logger.warning(
                "Skipping row %s: one or more required cells are empty.",
                row_number,
            )
            continue

        domains.append({
            "lead": lead,
            "domain": domain,
            "domain_type": domain_type,
            "employerId": employer_id,
        })

    # Only process rows assigned to Hari Prasad (case-insensitive match).
    domains = [
        item for item in domains
        if item["lead"].strip().casefold() == TARGET_LEAD.casefold()
    ]

    if not domains:
        raise ValueError(
            f"No valid domain records found for Lead '{TARGET_LEAD}' "
            f"in the '{INPUT_WORKSHEET}' worksheet."
        )

    logger.info(
        "Loaded %s domain records for Lead '%s' from '%s'.",
        len(domains),
        TARGET_LEAD,
        INPUT_WORKSHEET,
    )
    return domains


# ---------------------------------------------------------------------------
# MONGODB AGGREGATION
# ---------------------------------------------------------------------------

PIPELINE = [
    {
        "$match": {
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True,
            "createdDt": {"$type": "date"},
        }
    },
    {
        "$group": {
            "_id": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$createdDt",
                    "timezone": "UTC",
                }
            },
            "views": {"$sum": 1},
        }
    },
    {"$sort": {"_id": 1}},
]


def get_pipeline_for_employer(employer_id):
    """Return a pipeline with the current employer ID."""
    pipeline = [dict(stage) for stage in PIPELINE]
    pipeline[0] = {
        "$match": {
            **PIPELINE[0]["$match"],
            "employerId": employer_id,
        }
    }
    return pipeline


def aggregate_collection(collection, employer_id):
    pipeline = get_pipeline_for_employer(employer_id)

    results = collection.aggregate(
        pipeline,
        allowDiskUse=True,
        hint="employerId_1",
    )

    return {
        result["_id"]: result["views"]
        for result in results
        if result.get("_id")
    }


def process_employer(item):
    """Get daily Google views for one domain."""
    employer_id = item["employerId"]
    domain_type = item["domain_type"].strip().lower()
    started = time.time()

    if domain_type == "proxy":
        # Proxy: only this collection.
        collections = [PROD_DB["userAnalytics"]]
    else:
        # Direct Apply: query both collections and add daily counts.
        collections = [
            DC_DB["userAnalytics"],
            DC_DB["userAnalytics_prod"],
        ]

    combined_daily_map = defaultdict(int)

    try:
        for collection in collections:
            collection_map = aggregate_collection(
                collection,
                employer_id,
            )

            for date_string, views in collection_map.items():
                combined_daily_map[date_string] += views

            logger.info(
                "[%s] %s | %s: %s views",
                item["lead"],
                item["domain"],
                collection.name,
                sum(collection_map.values()),
            )

        daily_map = dict(combined_daily_map)

        logger.info(
            "Completed [%s] %s | Combined views: %s | Days: %s | %.1fs",
            item["lead"],
            item["domain"],
            sum(daily_map.values()),
            len(daily_map),
            time.time() - started,
        )

        return item, daily_map

    except Exception:
        logger.exception(
            "Failed [%s] %s | employerId=%s",
            item["lead"],
            item["domain"],
            employer_id,
        )
        # Fail this employer explicitly rather than reporting a partial
        # total if one of the required collections cannot be queried.
        raise


# ---------------------------------------------------------------------------
# REPORT BUILDING
# ---------------------------------------------------------------------------

def build_rows_for_items(items, daily_views_map):
    summary_rows = []
    monthly_rows = []

    for item in items:
        employer_id = item["employerId"]
        daily_map = daily_views_map.get(employer_id, {})

        if daily_map:
            max_date, max_clicks = max(
                daily_map.items(),
                key=lambda pair: pair[1],
            )
        else:
            max_date, max_clicks = "N/A", 0

        yesterday_clicks = daily_map.get(YESTERDAY_STR, 0)

        monthly_totals = defaultdict(int)
        for date_string, views in daily_map.items():
            monthly_totals[date_string[:7]] += views

        total_views = sum(monthly_totals.values())

        summary_rows.append({
            "Lead": item["lead"],
            "Domain": item["domain"],
            "Domain Type": item["domain_type"],
            "EmployerId": employer_id,
            "Max Clicks (Single Day)": max_clicks,
            "Max Clicks Date": max_date,
            f"Yesterday Clicks ({YESTERDAY_STR})": yesterday_clicks,
            "Total Views (Day 1 - Present)": total_views,
        })

        for year_month in sorted(monthly_totals):
            year, month = year_month.split("-")

            monthly_rows.append({
                "Lead": item["lead"],
                "Domain": item["domain"],
                "Domain Type": item["domain_type"],
                "EmployerId": employer_id,
                "Year": int(year),
                "Month": int(month),
                "Year-Month": year_month,
                "Views": monthly_totals[year_month],
            })

    return summary_rows, monthly_rows


# ---------------------------------------------------------------------------
# GOOGLE SHEETS OUTPUT
# ---------------------------------------------------------------------------

def get_or_create_worksheet(spreadsheet, title, rows_needed, cols_needed):
    """Get a Lead worksheet or create it if it does not exist."""
    safe_title = title[:100]

    try:
        worksheet = spreadsheet.worksheet(safe_title)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=safe_title,
            rows=max(rows_needed, 100),
            cols=max(cols_needed, 15),
        )

    # Ensure the worksheet is large enough for the new report.
    if worksheet.row_count < rows_needed:
        worksheet.add_rows(rows_needed - worksheet.row_count)

    if worksheet.col_count < cols_needed:
        worksheet.add_cols(cols_needed - worksheet.col_count)

    return worksheet


def push_lead_to_google_sheet(spreadsheet, lead, lead_summary, lead_monthly):
    """
    Write one Lead's summary and monthly data to its own worksheet.
    The Domains input worksheet is never changed.
    """
    with GSHEET_LOCK:
        summary_headers = [
            "Lead",
            "Domain",
            "Domain Type",
            "EmployerId",
            "Max Clicks (Single Day)",
            "Max Clicks Date",
            f"Yesterday Clicks ({YESTERDAY_STR})",
            "Total Views (Day 1 - Present)",
        ]

        monthly_headers = [
            "Lead",
            "Domain",
            "Domain Type",
            "EmployerId",
            "Year",
            "Month",
            "Year-Month",
            "Views",
        ]

        sheet_data = [
            [f"{lead.upper()} - DOMAIN VIEWS & CLICKS REPORT"],
            [
                "Generated at: "
                + datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
            ],
            [],
            ["SECTION 1: DOMAIN PERFORMANCE SUMMARY"],
            summary_headers,
        ]

        for row in lead_summary:
            sheet_data.append([
                row.get(header, "") for header in summary_headers
            ])

        # Add spacing before the monthly section.
        sheet_data.extend([
            [],
            [],
            ["SECTION 2: MONTHLY VIEWS FROM DAY 1"],
            monthly_headers,
        ])

        monthly_header_row = len(sheet_data)

        for row in lead_monthly:
            sheet_data.append([
                row.get(header, "") for header in monthly_headers
            ])

        required_rows = len(sheet_data) + 5
        required_cols = max(len(summary_headers), len(monthly_headers))

        worksheet = get_or_create_worksheet(
            spreadsheet,
            lead,
            required_rows,
            required_cols,
        )

        # Clear previous report values and formatting, then write fresh data.
        worksheet.clear()
        worksheet.update(
            values=sheet_data,
            range_name="A1",
            value_input_option="USER_ENTERED",
        )

        # Format title, section labels, and both header rows.
        summary_header_row = 5

        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": required_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": NAVY,
                            "textFormat": {
                                "bold": True,
                                "fontSize": 14,
                                "foregroundColor": WHITE,
                            },
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": summary_header_row - 1,
                        "endRowIndex": summary_header_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(summary_headers),
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": BLUE,
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": WHITE,
                            },
                            "horizontalAlignment": "CENTER",
                            "wrapStrategy": "WRAP",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": monthly_header_row - 1,
                        "endRowIndex": monthly_header_row,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(monthly_headers),
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": BLUE,
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": WHITE,
                            },
                            "horizontalAlignment": "CENTER",
                            "wrapStrategy": "WRAP",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 3,
                        "endRowIndex": 4,
                        "startColumnIndex": 0,
                        "endColumnIndex": required_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 12}
                        }
                    },
                    "fields": "userEnteredFormat.textFormat",
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": monthly_header_row - 2,
                        "endRowIndex": monthly_header_row - 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": required_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "fontSize": 12}
                        }
                    },
                    "fields": "userEnteredFormat.textFormat",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {"frozenRowCount": 5},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]

        spreadsheet.batch_update({"requests": requests})

        # Set readable column widths.
        width_requests = []
        for column_index in range(required_cols):
            width = 170
            if column_index in (1, 3):
                width = 230
            elif column_index in (4, 7):
                width = 190

            width_requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": column_index,
                        "endIndex": column_index + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            })

        spreadsheet.batch_update({"requests": width_requests})

        logger.info(
            "Updated Google Sheets tab '%s': %s summary rows, %s monthly rows.",
            lead,
            len(lead_summary),
            len(lead_monthly),
        )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    started = time.time()
    spreadsheet = connect_google_sheets()

    # 1. Read input from the Domains tab.
    domains_list = fetch_domains_from_sheet(spreadsheet)

    # 2. Group input by Lead.
    lead_groups = defaultdict(list)
    for item in domains_list:
        lead_groups[item["lead"]].append(item)

    # 3. Separate Direct Apply and Proxy work.
    direct_apply_items = [
        item for item in domains_list
        if item["domain_type"].strip().lower() != "proxy"
    ]
    proxy_items = [
        item for item in domains_list
        if item["domain_type"].strip().lower() == "proxy"
    ]

    logger.info(
        "Starting report only for Lead %s: %s Direct Apply domains (%s workers) and "
        "%s Proxy domains (%s workers).",
        TARGET_LEAD,
        len(direct_apply_items),
        DC_WORKERS,
        len(proxy_items),
        PROXY_WORKERS,
    )

    daily_views_map = {}

    # 4. Query MongoDB concurrently.
    with (
        ThreadPoolExecutor(max_workers=DC_WORKERS) as dc_pool,
        ThreadPoolExecutor(max_workers=PROXY_WORKERS) as proxy_pool,
    ):
        futures = []

        futures.extend(
            dc_pool.submit(process_employer, item)
            for item in direct_apply_items
        )
        futures.extend(
            proxy_pool.submit(process_employer, item)
            for item in proxy_items
        )

        for future in as_completed(futures):
            item, daily_map = future.result()
            daily_views_map[item["employerId"]] = daily_map

    # 5. Build and publish each Lead's report to Google Sheets.
    total_summary_rows = 0
    total_monthly_rows = 0

    for lead, lead_items in lead_groups.items():
        lead_summary, lead_monthly = build_rows_for_items(
            lead_items,
            daily_views_map,
        )

        push_lead_to_google_sheet(
            spreadsheet,
            lead,
            lead_summary,
            lead_monthly,
        )

        total_summary_rows += len(lead_summary)
        total_monthly_rows += len(lead_monthly)

    elapsed = time.time() - started

    print("\n" + "=" * 65)
    print(f"GOOGLE SHEETS REPORT COMPLETED - {TARGET_LEAD}")
    print("=" * 65)
    print(f"Input domains       : {len(domains_list)}")
    print(f"Lead worksheets     : {len(lead_groups)}")
    print(f"Summary rows        : {total_summary_rows}")
    print(f"Monthly rows        : {total_monthly_rows}")
    print(f"Yesterday (UTC)     : {YESTERDAY_STR}")
    print(f"Google spreadsheet  : https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
    print(f"Total time          : {elapsed:.2f} seconds")
    print("=" * 65)

    PROD_CLIENT.close()
    DC_CLIENT.close()
    ROOT_CLIENT.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Report generation failed.")
        raise
