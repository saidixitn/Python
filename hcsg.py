"""HCSG Google Jobs views analysis -> Google Sheets.

Counts one qualifying userAnalytics document as one Google-originated view.
Month is derived from viewDate, falling back to createdDt. The report retains
unmatched analytics records and flags possible duplicate uniqueId values; it
never silently drops them.
"""

import os
import logging
from collections import defaultdict, Counter
from datetime import datetime, timezone
from typing import Any

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from pymongo import MongoClient


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
EMPLOYER_ID = "6a904f26060e8f0b78b0dc81"
SPREADSHEET_ID = "1c3WqKgewVn0mqQTsH4pQzuR8P9JK6xI5QJ2aXLsekQk"
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"
PROD_DATABASE = "prod_jobiak_ai"
JOB_COLLECTION = "job"
ANALYTICS_COLLECTION = "userAnalytics"
BATCH_SIZE = 2000

# The script refreshes only these named tabs; all other spreadsheet tabs remain untouched.
TAB_OVERVIEW = "HCSG Overview"
TAB_LOCATION_TREND = "Location Monthly Trend"
TAB_LOCATION_STATUS = "Location Status Trend"
TAB_MONTHLY_SUMMARY = "Monthly Summary"
TAB_JOB_TREND = "Job Monthly Trend"
TAB_JOB_DETAILS = "Job View Details"
TAB_DATA_QUALITY = "Data Quality"

GOOGLE_VIEW_FILTER = {
    "employerId": EMPLOYER_ID,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("hcsg_views_report")


# ---------------------------------------------------------------------------
# CONNECTIONS
# ---------------------------------------------------------------------------
def connect_mongodb():
    if not MONGO_URI:
        raise ValueError("MONGO_URI is missing from .env")

    bootstrap = MongoClient(MONGO_URI, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)
    bootstrap.admin.command("ping")
    creds = bootstrap[CREDS_DATABASE][CREDS_COLLECTION].find_one(
        {"domain": PROD_DATABASE}, {"_id": 0, "mongo_uri": 1}
    )
    if not creds or not creds.get("mongo_uri"):
        bootstrap.close()
        raise ValueError(f"Mongo URI not found for {PROD_DATABASE} in {CREDS_DATABASE}.{CREDS_COLLECTION}")

    target = MongoClient(creds["mongo_uri"], serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)
    target.admin.command("ping")
    bootstrap.close()
    logger.info("Connected to %s", PROD_DATABASE)
    return target, target[PROD_DATABASE]


def connect_spreadsheet():
    if not os.path.isfile(GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(f"Google service-account JSON not found: {GOOGLE_CREDENTIALS_FILE}")
    credentials = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    spreadsheet = gspread.authorize(credentials).open_by_key(SPREADSHEET_ID)
    logger.info("Connected to Google spreadsheet: %s", spreadsheet.title)
    return spreadsheet


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_datetime(value: Any):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def format_value(value: Any):
    if value is None:
        return ""
    if isinstance(value, datetime):
        parsed = parse_datetime(value)
        return parsed.strftime("%Y-%m-%d %H:%M:%S UTC") if parsed else str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def month_for(analytics: dict) -> str:
    # viewDate is the event timestamp; createdDt is a fallback only.
    dt = parse_datetime(analytics.get("viewDate")) or parse_datetime(analytics.get("createdDt"))
    return dt.strftime("%Y-%m") if dt else "Unknown"


def classify_job(job: dict | None) -> str:
    if not job:
        return "Unmatched"
    status = text(job.get("status")).lower()
    active = job.get("isActive")
    if status == "posted" and active is True:
        return "Posted"
    if status in {"removed", "expired", "deleted"} or active is False:
        return "Expired"
    return "Other / Unknown"


def normalized_location(value: Any) -> str:
    value = " ".join(text(value).split())
    return value if value else "Unknown"


def pct_change(current, previous):
    if previous in (None, 0):
        return ""
    return (current - previous) / previous


def safe_key(value: Any) -> str:
    return text(value)


# ---------------------------------------------------------------------------
# FETCH JOBS AND BUILD LOOKUPS
# ---------------------------------------------------------------------------
def fetch_jobs(database):
    projection = {
        "_id": 0, "jobId": 1, "clientJobId": 1, "jobPubJobId": 1,
        "title": 1, "location": 1, "status": 1, "isActive": 1,
        "datePosted": 1, "validThrough": 1, "submittedUrl": 1,
    }
    cursor = database[JOB_COLLECTION].find({"employerId": EMPLOYER_ID}, projection, batch_size=BATCH_SIZE)
    jobs_by_alias = defaultdict(dict)
    jobs_by_id = {}
    try:
        for job in cursor:
            job_id = safe_key(job.get("jobId"))
            if job_id:
                jobs_by_id[job_id] = job
            for field in ("jobId", "clientJobId", "jobPubJobId"):
                alias = safe_key(job.get(field))
                if alias:
                    # Dict keyed by jobId prevents one job matching itself
                    # multiple times when aliases happen to share a value.
                    jobs_by_alias[alias][job_id or str(id(job))] = job
    finally:
        cursor.close()
    logger.info("Loaded %s HCSG job documents", len(jobs_by_id))
    return jobs_by_alias, jobs_by_id


def match_job(analytics, jobs_by_alias, jobs_by_id):
    # Try the most specific analytics identifiers first. If an alias maps to
    # multiple job records, prefer the exact jobId match; otherwise flag it.
    for field in ("jobPubJobId", "childJobId"):
        key = safe_key(analytics.get(field))
        if not key:
            continue
        if key in jobs_by_id:
            return jobs_by_id[key], False
        matches = list(jobs_by_alias.get(key, {}).values())
        if len(matches) == 1:
            return matches[0], False
        if len(matches) > 1:
            # Do not guess which job owns this view. Keep it unmatched and
            # surface the ambiguous join in the Data Quality tab.
            return None, True
    return None, False


# ---------------------------------------------------------------------------
# READ ANALYTICS AND AGGREGATE
# ---------------------------------------------------------------------------
def collect_views(database, jobs_by_alias, jobs_by_id):
    projection = {
        "_id": 0, "jobPubJobId": 1, "childJobId": 1, "jobtitle": 1,
        "location": 1, "company": 1, "submittedUrl": 1, "gpost_date": 1,
        "createdDt": 1, "viewDate": 1, "employerId": 1, "uniqueId": 1,
        "ipAddress": 1,
    }
    cursor = database[ANALYTICS_COLLECTION].find(GOOGLE_VIEW_FILTER, projection, batch_size=BATCH_SIZE)

    # One record = one qualifying view. No deduplication is applied.
    job_month = defaultdict(lambda: {"views": 0, "job": None, "info": None})
    location_month = Counter()
    location_status_month = Counter()
    month_totals = Counter()
    month_status = Counter()
    unique_ids = Counter()
    missing_month = 0
    missing_location = 0
    unmatched = 0
    ambiguous_matches = 0
    total = 0

    try:
        for analytics in cursor:
            total += 1
            job, ambiguous = match_job(analytics, jobs_by_alias, jobs_by_id)
            if ambiguous:
                ambiguous_matches += 1

            month = month_for(analytics)
            if month == "Unknown":
                missing_month += 1
            if job:
                job_key = safe_key(job.get("jobId")) or safe_key(analytics.get("jobPubJobId") or analytics.get("childJobId"))
                title = text(job.get("title")) or text(analytics.get("jobtitle")) or "Untitled"
                location = normalized_location(job.get("location") or analytics.get("location"))
                status = text(job.get("status")) or "Unknown"
                classification = classify_job(job)
            else:
                unmatched += 1
                job_key = safe_key(analytics.get("jobPubJobId") or analytics.get("childJobId")) or "No Job ID"
                title = text(analytics.get("jobtitle")) or "Unknown"
                location = normalized_location(analytics.get("location"))
                status = "Job record not found"
                classification = "Unmatched"
            if location == "Unknown":
                missing_location += 1

            unique_id = safe_key(analytics.get("uniqueId"))
            if unique_id:
                unique_ids[unique_id] += 1

            # Group at job x location x month. Keep title/status for details.
            key = (job_key, month, location)
            record = job_month[key]
            record["views"] += 1
            record["job"] = job
            record["info"] = {
                "title": title, "location": location, "status": status,
                "classification": classification, "month": month,
                "submittedUrl": text((job or {}).get("submittedUrl") or analytics.get("submittedUrl")),
                "jobPubJobId": text((job or {}).get("jobPubJobId") or analytics.get("jobPubJobId")),
                "clientJobId": text((job or {}).get("clientJobId")),
            }

            location_month[(location, month)] += 1
            location_status_month[(location, classification, month)] += 1
            month_totals[month] += 1
            month_status[(month, classification)] += 1
    finally:
        cursor.close()

    duplicate_unique_ids = sum(count - 1 for count in unique_ids.values() if count > 1)
    quality = {
        "Total qualifying analytics records": total,
        "Unmatched analytics records": unmatched,
        "Ambiguous job-ID matches": ambiguous_matches,
        "Records with unknown month": missing_month,
        "Records with unknown location": missing_location,
        "Duplicate uniqueId occurrences beyond first": duplicate_unique_ids,
        "Distinct non-empty uniqueId values": len(unique_ids),
        "Job documents loaded": len(jobs_by_id),
    }
    return job_month, location_month, location_status_month, month_totals, month_status, quality


# ---------------------------------------------------------------------------
# BUILD MONTH PIVOTS / ANALYSIS TABLES
# ---------------------------------------------------------------------------
def build_month_list(*counters):
    months = set()
    for counter in counters:
        for key in counter:
            month = key[-1] if isinstance(key, tuple) else key
            if month != "Unknown":
                months.add(month)
    return sorted(months)


def build_location_trend(location_month, months):
    locations = sorted({location for location, _ in location_month}, key=str.lower)
    headers = ["Location"] + months + ["Total Views", "Latest Month Views", "Previous Month Views", "MoM Change %", "Trend"]
    rows = []
    latest, previous = (months[-1], months[-2]) if len(months) >= 2 else ((months[-1], None) if months else (None, None))
    for location in locations:
        values = [location_month.get((location, month), 0) for month in months]
        total = sum(values)
        current = location_month.get((location, latest), 0) if latest else 0
        prior = location_month.get((location, previous), 0) if previous else None
        change = pct_change(current, prior) if prior is not None else ""
        if prior is None:
            trend = "Not enough months"
        elif current > prior:
            trend = "Increasing"
        elif current < prior:
            trend = "Decreasing"
        else:
            trend = "Flat"
        rows.append([location] + values + [total, current, prior if prior is not None else "", change, trend])
    return headers, rows


def build_location_status_trend(location_status_month, months):
    keys = sorted({(loc, status) for loc, status, _ in location_status_month}, key=lambda x: (x[0].lower(), x[1]))
    headers = ["Location", "Posting Classification"] + months + ["Total Views"]
    rows = []
    for location, status in keys:
        values = [location_status_month.get((location, status, month), 0) for month in months]
        rows.append([location, status] + values + [sum(values)])
    return headers, rows


def build_monthly_summary(month_totals, month_status, job_month, months):
    headers = ["Month", "Total Views", "Unique Jobs Viewed", "Avg Views per Job",
               "Posted Job Views", "Expired Job Views", "Other / Unknown Views",
               "Unmatched Views", "MoM Change %"]
    jobs_per_month = defaultdict(set)
    for (job_id, month, _location), record in job_month.items():
        if month != "Unknown":
            jobs_per_month[month].add(job_id)
    rows = []
    prior = None
    for month in months:
        total = month_totals.get(month, 0)
        unique_jobs = len(jobs_per_month.get(month, set()))
        avg_views = round(total / unique_jobs, 2) if unique_jobs else 0
        posted = month_status.get((month, "Posted"), 0)
        expired = month_status.get((month, "Expired"), 0)
        other = month_status.get((month, "Other / Unknown"), 0)
        unmatched = month_status.get((month, "Unmatched"), 0)
        change = pct_change(total, prior) if prior is not None else ""
        rows.append([month, total, unique_jobs, avg_views, posted, expired, other, unmatched, change])
        prior = total
    return headers, rows


def build_job_trend(job_month, months):
    by_job = defaultdict(lambda: {"title": "", "location": "", "classification": "", "values": Counter(), "total": 0})
    for (job_id, month, location), record in job_month.items():
        info = record["info"] or {}
        item = by_job[(job_id, location)]
        item["title"] = info.get("title", "")
        item["location"] = location
        item["classification"] = info.get("classification", "")
        item["values"][month] += record["views"]
        item["total"] += record["views"]
    headers = ["Job ID", "Job Title", "Location", "Posting Classification"] + months + ["Total Views"]
    ordered = sorted(by_job.items(), key=lambda x: (-x[1]["total"], x[1]["title"].lower()))
    rows = []
    for (job_id, _), item in ordered:
        rows.append([job_id, item["title"], item["location"], item["classification"]]
                    + [item["values"].get(month, 0) for month in months] + [item["total"]])
    return headers, rows


def build_job_details(job_month):
    headers = ["Employer ID", "Job ID", "Client Job ID", "Job Pub Job ID", "Job Title", "Location",
               "Job Status", "Is Active", "Posting Classification", "Date Posted", "Valid Through",
               "Month", "Views", "Submitted URL"]
    rows = []
    for (job_id, month, location), record in sorted(job_month.items(), key=lambda x: (x[0][1], x[0][2].lower(), x[0][0])):
        job = record["job"] or {}
        info = record["info"] or {}
        rows.append([
            EMPLOYER_ID, format_value(job.get("jobId")) or job_id,
            format_value(job.get("clientJobId")) or info.get("clientJobId", ""),
            format_value(job.get("jobPubJobId")) or info.get("jobPubJobId", ""),
            info.get("title", ""), location,
            format_value(job.get("status")) or info.get("status", ""),
            format_value(job.get("isActive")), info.get("classification", "Unmatched"),
            format_value(job.get("datePosted")), format_value(job.get("validThrough")),
            month, record["views"], info.get("submittedUrl", ""),
        ])
    return headers, rows


def build_overview(month_totals, location_month, job_month, quality, months):
    total_views = sum(month_totals.values())
    locations = {loc for loc, _ in location_month}
    jobs = {job_id for job_id, _, _ in job_month}
    latest_month = months[-1] if months else ""
    previous_month = months[-2] if len(months) > 1 else ""
    latest_views = month_totals.get(latest_month, 0) if latest_month else 0
    previous_views = month_totals.get(previous_month, 0) if previous_month else None
    change = pct_change(latest_views, previous_views) if previous_views is not None else ""
    headers = ["Metric", "Value", "Notes"]
    rows = [
        ["Employer ID", EMPLOYER_ID, "HCSG employerId supplied for the report"],
        ["Total Google views", total_views, "Count of qualifying userAnalytics documents"],
        ["Months covered", len(months), f"{months[0]} to {months[-1]}" if months else "No dated records"],
        ["Locations with views", len(locations), "Based on normalized job/analytics location"],
        ["Jobs with views", len(jobs), "Distinct matched or analytics job identifiers"],
        ["Latest month", latest_month, "Latest month found in source data"],
        ["Latest month views", latest_views, "May be partial if the month is still in progress"],
        ["Previous month", previous_month, "Immediately preceding month present in the data"],
        ["Previous month views", previous_views if previous_views is not None else "", ""],
        ["Latest month MoM change", change, "Blank when there is no comparable previous month or previous views are zero"],
    ]
    rows.extend([[key, value, "Data quality / reconciliation indicator"] for key, value in quality.items()])
    return headers, rows


def build_data_quality(quality):
    headers = ["Check", "Count", "Interpretation / Action"]
    notes = {
        "Total qualifying analytics records": "Total records matching the supplied HCSG Google-view filter; each record is counted as one view.",
        "Unmatched analytics records": "No matching job document found. Review identifier mapping and jobs removed from the job collection.",
        "Ambiguous job-ID matches": "An analytics identifier matched multiple job documents. Confirm the correct join key before using these rows for job-level conclusions.",
        "Records with unknown month": "Both viewDate and createdDt were missing or unparsable; these records are excluded from month pivots but remain in job detail under Unknown.",
        "Records with unknown location": "Location missing from both the matched job and analytics record.",
        "Duplicate uniqueId occurrences beyond first": "Potential repeated event identifiers. Flag only; not removed from view totals.",
        "Distinct non-empty uniqueId values": "Count of distinct non-empty uniqueId values in the filtered analytics records.",
        "Job documents loaded": "All job documents for the HCSG employerId, regardless of current status.",
    }
    return headers, [[key, value, notes.get(key, "Review") ] for key, value in quality.items()]


# ---------------------------------------------------------------------------
# GOOGLE SHEETS WRITING / FORMATTING
# ---------------------------------------------------------------------------
def get_or_create_worksheet(spreadsheet, title, columns, rows):
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=max(rows, 100), cols=max(columns, 10))
    return ws


def write_tab(spreadsheet, title, headers, rows, percentage_columns=None):
    values = [headers] + rows
    ws = get_or_create_worksheet(spreadsheet, title, len(headers), len(values) + 10)
    ws.clear()
    if ws.row_count < len(values):
        ws.add_rows(len(values) - ws.row_count)
    if ws.col_count < len(headers):
        ws.add_cols(len(headers) - ws.col_count)
    if values:
        ws.update(range_name="A1", values=values, value_input_option="USER_ENTERED")
    ws.freeze(rows=1)
    last_col = gspread.utils.rowcol_to_a1(1, len(headers))
    ws.format(f"A1:{last_col}", {
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": {"red": 0.12, "green": 0.28, "blue": 0.48},
        "wrapStrategy": "WRAP", "verticalAlignment": "MIDDLE",
    })
    ws.format("A1:" + gspread.utils.rowcol_to_a1(max(1, len(values)), len(headers)), {"verticalAlignment": "MIDDLE"})
    if percentage_columns:
        for col in percentage_columns:
            if len(values) > 1:
                col_letter = gspread.utils.rowcol_to_a1(1, col).rstrip("1")
                ws.format(f"{col_letter}2:{col_letter}{len(values)}", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%;[Red]-0.0%"}})
    if title in {TAB_LOCATION_TREND, TAB_LOCATION_STATUS, TAB_JOB_TREND}:
        ws.format("A:A", {"textFormat": {"bold": True}})
    logger.info("Updated '%s' (%s rows x %s columns)", title, len(rows), len(headers))


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    mongo_client = None
    try:
        mongo_client, database = connect_mongodb()
        spreadsheet = connect_spreadsheet()
        jobs_by_alias, jobs_by_id = fetch_jobs(database)
        (job_month, location_month, location_status_month,
         month_totals, month_status, quality) = collect_views(database, jobs_by_alias, jobs_by_id)

        months = build_month_list(location_month, location_status_month, month_totals)
        if "Unknown" in month_totals:
            # Unknown month records are shown in details and quality checks, not as a month column.
            month_totals.pop("Unknown", None)

        location_headers, location_rows = build_location_trend(location_month, months)
        status_headers, status_rows = build_location_status_trend(location_status_month, months)
        summary_headers, summary_rows = build_monthly_summary(month_totals, month_status, job_month, months)
        job_headers, job_rows = build_job_trend(job_month, months)
        detail_headers, detail_rows = build_job_details(job_month)
        overview_headers, overview_rows = build_overview(month_totals, location_month, job_month, quality, months)
        quality_headers, quality_rows = build_data_quality(quality)

        write_tab(spreadsheet, TAB_OVERVIEW, overview_headers, overview_rows)
        write_tab(spreadsheet, TAB_LOCATION_TREND, location_headers, location_rows,
                  percentage_columns=[len(location_headers) - 2])
        write_tab(spreadsheet, TAB_LOCATION_STATUS, status_headers, status_rows)
        write_tab(spreadsheet, TAB_MONTHLY_SUMMARY, summary_headers, summary_rows,
                  percentage_columns=[len(summary_headers)])
        write_tab(spreadsheet, TAB_JOB_TREND, job_headers, job_rows)
        write_tab(spreadsheet, TAB_JOB_DETAILS, detail_headers, detail_rows)
        write_tab(spreadsheet, TAB_DATA_QUALITY, quality_headers, quality_rows)

        logger.info("=" * 65)
        logger.info("HCSG Google views analysis completed")
        logger.info("Qualifying views: %s | Jobs with views: %s | Locations: %s | Months: %s",
                    quality["Total qualifying analytics records"], len({k[0] for k in job_month}),
                    len({k[2] for k in job_month}), len(months))
        logger.info("Unmatched: %s | Ambiguous matches: %s | Potential duplicate uniqueIds: %s",
                    quality["Unmatched analytics records"], quality["Ambiguous job-ID matches"],
                    quality["Duplicate uniqueId occurrences beyond first"])
        logger.info("=" * 65)
    finally:
        if mongo_client:
            mongo_client.close()


if __name__ == "__main__":
    main()
