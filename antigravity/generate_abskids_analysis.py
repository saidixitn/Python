"""
ABS Kids Full Views & Googlebot Analysis + Title + Location CSV (Both Dates)
==========================================================================
Client: ABS Kids (abskids.com/gfj/)
EmployerId: 6aa8d214060e8f0b78b0dc87
Database: prod_jobiak_ai (collections: job, userAnalytics)

Generates:
1. ABS_Kids_Views_and_No_Bot_Analysis.xlsx (6 styled tabs matching HCSG format)
2. ABS_Kids_Title_Location_Both_Dates.csv (Title + Location breakdown with
   Max Clicks Date 2026-10-12, Yesterday 2026-11-11, Total Views, Bot Visits,
   and Date Posted / Valid Through ranges)
"""

import os
import csv
import logging
from collections import defaultdict
from datetime import datetime, timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("abskids_analysis")

EMP_ID = "6aa8d214060e8f0b78b0dc87"
DATE_1_STR = "2026-11-10"
DATE_2_STR = "2026-11-11"


def format_date(val):
    if not val:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def style_worksheet(ws, title_text, headers, rows):
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    ws.views.sheetView[0].showGridLines = True
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=title_text)
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1B365D")
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.row_dimensions[3].height = 24
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    col_widths = {col_idx: len(str(h)) for col_idx, h in enumerate(headers, 1)}
    for row_idx, r in enumerate(rows, 4):
        ws.row_dimensions[row_idx].height = 19
        for col_idx, val in enumerate(r, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if isinstance(val, int):
                    cell.number_format = "#,##0"
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if row_idx <= 104:
                val_len = len(str(val or ""))
                if val_len > col_widths[col_idx]:
                    col_widths[col_idx] = val_len

    for col_idx, max_len in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 4, 12), 55)

    ws.freeze_panes = "A4"


def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI is missing from .env")

    logger.info("Connecting to MongoDB...")
    primary_client = MongoClient(mongo_uri)
    creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
    if not creds:
        raise ValueError("prod_jobiak_ai creds not found")

    prod_client = MongoClient(creds["mongo_uri"])
    db = prod_client["prod_jobiak_ai"]
    jobs_col = db["job"]
    analytics_col = db["userAnalytics"]

    logger.info("Fetching ABS Kids jobs from prod_jobiak_ai.job...")
    projection = {
        "_id": 0, "jobId": 1, "clientJobId": 1, "title": 1, "location": 1,
        "status": 1, "isActive": 1, "datePosted": 1, "validThrough": 1, "submittedUrl": 1
    }
    jobs = list(jobs_col.find({"employerId": EMP_ID}, projection))
    logger.info(f"Loaded {len(jobs)} total ABS Kids jobs.")

    # 1. Aggregate Google human views per jobId + per date
    logger.info("Aggregating Google human views (all-time & by date)...")
    p_gviews = [
        {
            "$match": {
                "employerId": EMP_ID,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$type": "date"}
            }
        },
        {
            "$group": {
                "_id": {
                    "jobId": "$childJobId",
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}}
                },
                "views": {"$sum": 1}
            }
        }
    ]
    google_views_map = defaultdict(int)
    max_date_views_map = defaultdict(int)
    yest_date_views_map = defaultdict(int)

    for r in analytics_col.aggregate(p_gviews, allowDiskUse=True, hint="employerId_1"):
        jid = str(r["_id"].get("jobId") or "").strip()
        d_str = r["_id"].get("date")
        v = r["views"]
        if not jid:
            continue
        google_views_map[jid] += v
        if d_str == DATE_1_STR:
            max_date_views_map[jid] += v
        elif d_str == DATE_2_STR:
            yest_date_views_map[jid] += v

    # 2. Googlebot visits (isBot == True)
    logger.info("Aggregating Googlebot visits...")
    p_bot = [
        {"$match": {"employerId": EMP_ID, "isBot": True}},
        {"$group": {"_id": "$childJobId", "visits": {"$sum": 1}}}
    ]
    bot_visits_map = {
        str(r["_id"]): r["visits"]
        for r in analytics_col.aggregate(p_bot, allowDiskUse=True, hint="employerId_1")
        if r.get("_id")
    }

    # 3. Enrich jobs
    enriched_jobs = []
    for j in jobs:
        jid = str(j.get("jobId", "")).strip()
        v_count = google_views_map.get(jid, 0)
        v_max_dt = max_date_views_map.get(jid, 0)
        v_yest_dt = yest_date_views_map.get(jid, 0)
        b_visits = bot_visits_map.get(jid, 0)
        has_bot = "Yes" if b_visits > 0 else "No"

        title = (j.get("title") or "Unknown").strip()
        location = (j.get("location") or "Unknown").strip()
        is_posted = (j.get("status") == "posted" and j.get("isActive") is True)

        enriched_jobs.append({
            "jobId": jid,
            "clientJobId": str(j.get("clientJobId", "")).strip(),
            "title": title,
            "location": location,
            "status": str(j.get("status", "")).strip(),
            "isActive": j.get("isActive"),
            "datePosted": j.get("datePosted"),
            "validThrough": j.get("validThrough"),
            "submittedUrl": str(j.get("submittedUrl", "")).strip(),
            "views": v_count,
            "views_max_date": v_max_dt,
            "views_yest_date": v_yest_dt,
            "bot_visits": b_visits,
            "has_bot": has_bot,
            "is_posted": is_posted
        })

    # Aggregations
    def make_agg_dict():
        return {
            "total_jobs": 0, "posted_jobs": 0, "jobs_with_bot": 0, "jobs_no_bot": 0,
            "views": 0, "views_max_date": 0, "views_yest_date": 0, "bot_visits": 0,
            "min_date_posted": None, "max_valid_through": None
        }

    title_agg = defaultdict(make_agg_dict)
    loc_agg = defaultdict(make_agg_dict)
    combo_agg = defaultdict(make_agg_dict)

    for ej in enriched_jobs:
        for bucket, key in [(title_agg, ej["title"]), (loc_agg, ej["location"]), (combo_agg, (ej["title"], ej["location"]))]:
            d = bucket[key]
            d["total_jobs"] += 1
            if ej["is_posted"]:
                d["posted_jobs"] += 1
                if ej["bot_visits"] > 0:
                    d["jobs_with_bot"] += 1
                else:
                    d["jobs_no_bot"] += 1
            d["views"] += ej["views"]
            d["views_max_date"] += ej["views_max_date"]
            d["views_yest_date"] += ej["views_yest_date"]
            d["bot_visits"] += ej["bot_visits"]

            dp = ej["datePosted"]
            vt = ej["validThrough"]
            if isinstance(dp, datetime):
                if d["min_date_posted"] is None or dp < d["min_date_posted"]:
                    d["min_date_posted"] = dp
            if isinstance(vt, datetime):
                if d["max_valid_through"] is None or vt > d["max_valid_through"]:
                    d["max_valid_through"] = vt

    posted_all_jobs = sorted([ej for ej in enriched_jobs if ej["is_posted"]], key=lambda x: (x["views"], str(x["datePosted"] or "")), reverse=True)
    posted_no_bot_jobs = [ej for ej in posted_all_jobs if ej["bot_visits"] == 0]

    # ---------------------------------------------------------
    # EXPORT 1: TITLE + LOCATION CSV (WITH BOTH DATES)
    # ---------------------------------------------------------
    sorted_combos = sorted(combo_agg.items(), key=lambda x: (x[1]["views"], x[1]["total_jobs"]), reverse=True)
    csv_headers = [
        "Job Title", "Location", "Total Jobs", "Active Posted Jobs",
        "Jobs With Bot Visit", "Jobs With NO Bot Visit",
        f"Views ({DATE_1_STR})", f"Views ({DATE_2_STR})",
        "Total Views", "Total Bot Visits",
        "Earliest Date Posted", "Latest Valid Through"
    ]
    csv_rows = [
        [
            tl[0], tl[1], d["total_jobs"], d["posted_jobs"],
            d["jobs_with_bot"], d["jobs_no_bot"],
            d["views_max_date"], d["views_yest_date"],
            d["views"], d["bot_visits"],
            format_date(d["min_date_posted"]), format_date(d["max_valid_through"])
        ]
        for tl, d in sorted_combos
    ]

    csv_filename = "ABS_Kids_Title_Location_Both_Dates.csv"
    csv_paths = [
        os.path.join(r"C:\Users\JOBIAK\Documents\Python", csv_filename),
        os.path.join(r"C:\Users\JOBIAK\Downloads", csv_filename),
        os.path.join(r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6", csv_filename),
    ]
    for p in csv_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                writer.writerows(csv_rows)
            logger.info(f"Saved Title+Location CSV to {p}")
        except PermissionError:
            fallback_p = p.replace(".csv", "_10_11_Nov.csv")
            with open(fallback_p, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                writer.writerows(csv_rows)
            logger.info(f"File locked, saved fallback CSV to {fallback_p}")

    # ---------------------------------------------------------
    # EXPORT 2: FULL EXCEL ANALYSIS (MATCHING HCSG FORMAT)
    # ---------------------------------------------------------
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    total_posted = len(posted_all_jobs)
    total_no_bot = len(posted_no_bot_jobs)
    total_with_bot = total_posted - total_no_bot
    bot_cov = f"{(total_with_bot / total_posted * 100):.1f}%" if total_posted > 0 else "0%"

    ws_sum = wb.create_sheet(title="ABS Kids Overview")
    sum_rows = [
        ["Employer ID", EMP_ID, "ABS Kids (abskids.com/gfj/)"],
        ["Total Jobs in Database", len(jobs), "All ABS Kids job records in prod_jobiak_ai.job"],
        ["Active Posted Jobs", total_posted, "Jobs with status: 'posted' and isActive: True"],
        ["Posted Jobs WITH Bot Visits", total_with_bot, "Posted jobs crawled by Googlebot"],
        ["Posted Jobs with NO Bot Visit", total_no_bot, "Active posted jobs with 0 Googlebot visits"],
        ["Googlebot Crawl Coverage %", bot_cov, "Percentage of active posted jobs visited by Googlebot"],
        ["Total Views (All-Time)", sum(google_views_map.values()), "Total qualifying Google human views"],
        [f"Views on {DATE_1_STR}", sum(max_date_views_map.values()), f"Views on {DATE_1_STR}"],
        [f"Views on {DATE_2_STR}", sum(yest_date_views_map.values()), f"Views on {DATE_2_STR}"],
        ["Total Googlebot Visits", sum(bot_visits_map.values()), "Total Googlebot crawl visits"],
        ["Distinct Job Titles", len(title_agg), "Distinct job titles"],
        ["Distinct Locations", len(loc_agg), "Distinct locations"],
        ["Report Generated At (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "Timestamp"],
    ]
    style_worksheet(ws_sum, "ABS Kids - Executive Views & Googlebot Crawl Summary", ["Metric", "Value", "Description"], sum_rows)

    ws_title = wb.create_sheet(title="Title Wise Views")
    t_headers = ["Job Title", "Total Jobs", "Active Posted Jobs", "Jobs With Bot Visit", "Jobs With NO Bot Visit", f"Views ({DATE_1_STR})", f"Views ({DATE_2_STR})", "Total Views", "Total Bot Visits"]
    t_rows = [
        [t, d["total_jobs"], d["posted_jobs"], d["jobs_with_bot"], d["jobs_no_bot"], d["views_max_date"], d["views_yest_date"], d["views"], d["bot_visits"]]
        for t, d in sorted(title_agg.items(), key=lambda x: (x[1]["views"], x[1]["total_jobs"]), reverse=True)
    ]
    style_worksheet(ws_title, "ABS Kids - Title Wise Views & Bot Visits Analysis", t_headers, t_rows)

    ws_loc = wb.create_sheet(title="Location Wise Views")
    l_headers = ["Location", "Total Jobs", "Active Posted Jobs", "Jobs With Bot Visit", "Jobs With NO Bot Visit", f"Views ({DATE_1_STR})", f"Views ({DATE_2_STR})", "Total Views", "Total Bot Visits"]
    l_rows = [
        [l, d["total_jobs"], d["posted_jobs"], d["jobs_with_bot"], d["jobs_no_bot"], d["views_max_date"], d["views_yest_date"], d["views"], d["bot_visits"]]
        for l, d in sorted(loc_agg.items(), key=lambda x: (x[1]["views"], x[1]["total_jobs"]), reverse=True)
    ]
    style_worksheet(ws_loc, "ABS Kids - Location Wise Views & Bot Visits Analysis", l_headers, l_rows)

    ws_combo = wb.create_sheet(title="Title + Location Views")
    style_worksheet(ws_combo, "ABS Kids - Title + Location Views (10th & 11th Nov 2026)", csv_headers, csv_rows)

    ws_nobot = wb.create_sheet(title="Jobs With NO Bot Visit")
    job_headers = ["Job ID", "Client Job ID", "Job Title", "Location", "Status", "isActive", "Date Posted", "Valid Through", "Submitted URL", f"Views ({DATE_1_STR})", f"Views ({DATE_2_STR})", "Total Views", "Bot Visits"]
    nobot_rows = [
        [j["jobId"], j["clientJobId"], j["title"], j["location"], j["status"], str(j["isActive"]), format_date(j["datePosted"]), format_date(j["validThrough"]), j["submittedUrl"], j["views_max_date"], j["views_yest_date"], j["views"], j["bot_visits"]]
        for j in posted_no_bot_jobs
    ]
    style_worksheet(ws_nobot, f"ABS Kids - Active Posted Jobs With NO Googlebot Visit (Total: {len(nobot_rows)})", job_headers, nobot_rows)

    ws_all = wb.create_sheet(title="All Active Posted Jobs")
    all_rows = [
        [j["jobId"], j["clientJobId"], j["title"], j["location"], j["status"], str(j["isActive"]), format_date(j["datePosted"]), format_date(j["validThrough"]), j["submittedUrl"], j["views_max_date"], j["views_yest_date"], j["views"], j["bot_visits"]]
        for j in posted_all_jobs
    ]
    style_worksheet(ws_all, f"ABS Kids - All Active Posted Jobs Detail (Total: {len(all_rows)})", job_headers, all_rows)

    xlsx_filename = "ABS_Kids_Views_and_No_Bot_Analysis.xlsx"
    xlsx_paths = [
        os.path.join(r"C:\Users\JOBIAK\Documents\Python", xlsx_filename),
        os.path.join(r"C:\Users\JOBIAK\Downloads", xlsx_filename),
        os.path.join(r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6", xlsx_filename),
    ]
    for p in xlsx_paths:
        try:
            wb.save(p)
            logger.info(f"Saved Excel workbook to {p}")
        except PermissionError:
            fallback_p = p.replace(".xlsx", "_10_11_Nov.xlsx")
            wb.save(fallback_p)
            logger.info(f"File locked, saved fallback Excel workbook to {fallback_p}")

    print("\n" + "=" * 65)
    print("ABS KIDS ANALYSIS COMPLETED:")
    print(f"  Total Jobs: {len(jobs)} | Active Posted: {total_posted}")
    print(f"  With Bot: {total_with_bot} | NO Bot: {total_no_bot} ({bot_cov} coverage)")
    print(f"  Total Views: {sum(google_views_map.values())} | {DATE_1_STR}: {sum(max_date_views_map.values())} | {DATE_2_STR}: {sum(yest_date_views_map.values())}")
    print(f"  Title+Location CSV: {csv_paths[0]}")
    print(f"  Excel Analysis:     {xlsx_paths[0]}")
    print("=" * 65)


if __name__ == "__main__":
    main()
