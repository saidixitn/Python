import os
import re
import logging
from collections import defaultdict
from datetime import datetime, timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from dotenv import load_dotenv
from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("views_excel_generator")

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
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.views.sheetView[0].showGridLines = True

    # Title banner
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=title_text)
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1B365D")
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    # Table Header row at row 3
    ws.row_dimensions[3].height = 24
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Track column widths based on headers and sample rows (fast)
    col_widths = {col_idx: len(str(h)) for col_idx, h in enumerate(headers, 1)}

    # Data rows starting at row 4
    for row_idx, r in enumerate(rows, 4):
        ws.row_dimensions[row_idx].height = 19
        for col_idx, val in enumerate(r, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            
            # Alignments & formatting
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if isinstance(val, int):
                    cell.number_format = "#,##0"
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            # Sample first 100 rows for auto width
            if row_idx <= 104:
                val_len = len(str(val or ""))
                if val_len > col_widths[col_idx]:
                    col_widths[col_idx] = val_len

    # Set column dimensions
    for col_idx, max_len in col_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 55)

    ws.freeze_panes = "A4"

def generate_report_for_client(db, client_name, emp_id, filename_slug):
    jobs_col = db["job"]
    analytics_col = db["userAnalytics"]

    logger.info(f"=== Processing {client_name} ({emp_id}) ===")
    logger.info("Fetching jobs from prod_jobiak_ai.job...")
    projection = {
        "_id": 0, "jobId": 1, "clientJobId": 1, "title": 1, "location": 1,
        "status": 1, "isActive": 1, "datePosted": 1, "validThrough": 1, "submittedUrl": 1
    }
    jobs = list(jobs_col.find({"employerId": emp_id}, projection))
    logger.info(f"Loaded {len(jobs)} total jobs for {client_name}.")

    logger.info("Aggregating Google views (isFromGoogle: True)...")
    p_gviews = [
        {
            "$match": {
                "employerId": emp_id,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True
            }
        },
        {"$group": {"_id": "$childJobId", "views": {"$sum": 1}}}
    ]
    google_views_map = {
        str(r["_id"]): r["views"]
        for r in analytics_col.aggregate(p_gviews, allowDiskUse=True)
        if r.get("_id")
    }

    logger.info("Aggregating Googlebot visits (isBot: True)...")
    p_bot = [
        {"$match": {"employerId": emp_id, "isBot": True}},
        {"$group": {"_id": "$childJobId", "visits": {"$sum": 1}}}
    ]
    bot_visits_map = {
        str(r["_id"]): r["visits"]
        for r in analytics_col.aggregate(p_bot, allowDiskUse=True)
        if r.get("_id")
    }

    logger.info("Enriching job records...")
    enriched_jobs = []
    for j in jobs:
        jid = str(j.get("jobId", "")).strip()
        v_count = google_views_map.get(jid, 0)
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
            "bot_visits": b_visits,
            "has_bot": has_bot,
            "is_posted": is_posted
        })

    # Aggregation 1: Title Wise
    title_agg = defaultdict(lambda: {
        "total_jobs": 0, "posted_jobs": 0, "jobs_with_bot": 0, "jobs_no_bot": 0,
        "views": 0, "bot_visits": 0
    })
    for ej in enriched_jobs:
        t = ej["title"]
        title_agg[t]["total_jobs"] += 1
        if ej["is_posted"]:
            title_agg[t]["posted_jobs"] += 1
            if ej["bot_visits"] > 0:
                title_agg[t]["jobs_with_bot"] += 1
            else:
                title_agg[t]["jobs_no_bot"] += 1
        title_agg[t]["views"] += ej["views"]
        title_agg[t]["bot_visits"] += ej["bot_visits"]

    # Aggregation 2: Location Wise
    loc_agg = defaultdict(lambda: {
        "total_jobs": 0, "posted_jobs": 0, "jobs_with_bot": 0, "jobs_no_bot": 0,
        "views": 0, "bot_visits": 0
    })
    for ej in enriched_jobs:
        l = ej["location"]
        loc_agg[l]["total_jobs"] += 1
        if ej["is_posted"]:
            loc_agg[l]["posted_jobs"] += 1
            if ej["bot_visits"] > 0:
                loc_agg[l]["jobs_with_bot"] += 1
            else:
                loc_agg[l]["jobs_no_bot"] += 1
        loc_agg[l]["views"] += ej["views"]
        loc_agg[l]["bot_visits"] += ej["bot_visits"]

    # Aggregation 3: Title + Location Wise
    combo_agg = defaultdict(lambda: {
        "total_jobs": 0, "posted_jobs": 0, "jobs_with_bot": 0, "jobs_no_bot": 0,
        "views": 0, "bot_visits": 0
    })
    for ej in enriched_jobs:
        tl = (ej["title"], ej["location"])
        combo_agg[tl]["total_jobs"] += 1
        if ej["is_posted"]:
            combo_agg[tl]["posted_jobs"] += 1
            if ej["bot_visits"] > 0:
                combo_agg[tl]["jobs_with_bot"] += 1
            else:
                combo_agg[tl]["jobs_no_bot"] += 1
        combo_agg[tl]["views"] += ej["views"]
        combo_agg[tl]["bot_visits"] += ej["bot_visits"]

    # Filter 4: Posted Jobs With No Bot
    posted_no_bot_jobs = [
        ej for ej in enriched_jobs
        if ej["is_posted"] and ej["bot_visits"] == 0
    ]
    posted_no_bot_jobs.sort(key=lambda x: (x["views"], str(x["datePosted"] or "")), reverse=True)

    # All posted active jobs
    posted_all_jobs = [ej for ej in enriched_jobs if ej["is_posted"]]
    posted_all_jobs.sort(key=lambda x: (x["views"], str(x["datePosted"] or "")), reverse=True)

    logger.info("Building Excel workbook...")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ---------------- TAB 1: SUMMARY ----------------
    overview_title = f"{client_name[:25]} Overview"
    ws_summary = wb.create_sheet(title=overview_title)
    total_posted = len(posted_all_jobs)
    total_no_bot = len(posted_no_bot_jobs)
    total_with_bot = total_posted - total_no_bot
    bot_coverage_pct = f"{(total_with_bot / total_posted * 100):.1f}%" if total_posted > 0 else "0%"
    
    summary_headers = ["Metric", "Value", "Description"]
    summary_rows = [
        ["Employer ID", emp_id, f"Configured employer ID for {client_name}"],
        ["Company Name", client_name, "Employer Name"],
        ["Total Jobs in Database", len(jobs), f"All {client_name} job records in prod_jobiak_ai.job"],
        ["Active Posted Jobs", total_posted, "Jobs with status: 'posted' and isActive: True"],
        ["Posted Jobs WITH Bot Visits", total_with_bot, "Posted jobs crawled by Googlebot"],
        ["Posted Jobs with NO Bot Visit", total_no_bot, "Active posted jobs with 0 Googlebot visits"],
        ["Googlebot Crawl Coverage %", bot_coverage_pct, "Percentage of active posted jobs visited by Googlebot"],
        ["Total Views (Google: isFromGoogle = True)", sum(google_views_map.values()), "Total qualifying Google-originated views"],
        ["Total Googlebot Visits", sum(bot_visits_map.values()), "Total Googlebot crawl visits"],
        ["Distinct Job Titles", len(title_agg), f"Distinct job titles across {client_name} jobs"],
        ["Distinct Locations", len(loc_agg), f"Distinct locations across {client_name} jobs"],
        ["Report Generated At (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "Timestamp of data aggregation"]
    ]
    style_worksheet(ws_summary, f"{client_name} - Executive Views & Googlebot Crawl Summary", summary_headers, summary_rows)

    # ---------------- TAB 2: TITLE WISE ----------------
    ws_title = wb.create_sheet(title="Title Wise Views")
    title_headers = [
        "Job Title", "Total Jobs", "Active Posted Jobs", "Jobs With Bot Visit",
        "Jobs With NO Bot Visit", "Views", "Total Bot Visits"
    ]
    sorted_titles = sorted(title_agg.items(), key=lambda x: (x[1]["views"], x[1]["total_jobs"]), reverse=True)
    title_rows = [
        [
            t, d["total_jobs"], d["posted_jobs"], d["jobs_with_bot"], d["jobs_no_bot"],
            d["views"], d["bot_visits"]
        ]
        for t, d in sorted_titles
    ]
    style_worksheet(ws_title, f"{client_name} - Title Wise Views & Bot Visits Analysis", title_headers, title_rows)

    # ---------------- TAB 3: LOCATION WISE ----------------
    ws_loc = wb.create_sheet(title="Location Wise Views")
    loc_headers = [
        "Location", "Total Jobs", "Active Posted Jobs", "Jobs With Bot Visit",
        "Jobs With NO Bot Visit", "Views", "Total Bot Visits"
    ]
    sorted_locs = sorted(loc_agg.items(), key=lambda x: (x[1]["views"], x[1]["total_jobs"]), reverse=True)
    loc_rows = [
        [
            l, d["total_jobs"], d["posted_jobs"], d["jobs_with_bot"], d["jobs_no_bot"],
            d["views"], d["bot_visits"]
        ]
        for l, d in sorted_locs
    ]
    style_worksheet(ws_loc, f"{client_name} - Location Wise Views & Bot Visits Analysis", loc_headers, loc_rows)

    # ---------------- TAB 4: TITLE + LOCATION WISE ----------------
    ws_combo = wb.create_sheet(title="Title + Location Views")
    combo_headers = [
        "Job Title", "Location", "Total Jobs", "Active Posted Jobs", "Jobs With Bot Visit",
        "Jobs With NO Bot Visit", "Views", "Total Bot Visits"
    ]
    sorted_combos = sorted(combo_agg.items(), key=lambda x: (x[1]["views"], x[1]["total_jobs"]), reverse=True)
    combo_rows = [
        [
            tl[0], tl[1], d["total_jobs"], d["posted_jobs"], d["jobs_with_bot"], d["jobs_no_bot"],
            d["views"], d["bot_visits"]
        ]
        for tl, d in sorted_combos
    ]
    style_worksheet(ws_combo, f"{client_name} - Title + Location Views & Bot Visits Analysis", combo_headers, combo_rows)

    # ---------------- TAB 5: JOBS WITH NO BOT ----------------
    ws_nobot = wb.create_sheet(title="Jobs With NO Bot Visit")
    nobot_job_headers = [
        "Job ID", "Client Job ID", "Job Title", "Location", "Status", "isActive",
        "Date Posted", "Valid Through", "Submitted URL", "Views", "Bot Visits"
    ]
    nobot_job_rows = [
        [
            j["jobId"], j["clientJobId"], j["title"], j["location"], j["status"], str(j["isActive"]),
            format_date(j["datePosted"]), format_date(j["validThrough"]), j["submittedUrl"],
            j["views"], j["bot_visits"]
        ]
        for j in posted_no_bot_jobs
    ]
    style_worksheet(ws_nobot, f"{client_name} - Active Posted Jobs With NO Googlebot Visit (Total: {len(nobot_job_rows)})", nobot_job_headers, nobot_job_rows)

    # ---------------- TAB 6: ALL ACTIVE POSTED JOBS ----------------
    ws_all = wb.create_sheet(title="All Active Posted Jobs")
    all_job_headers = [
        "Job ID", "Client Job ID", "Job Title", "Location", "Status", "isActive",
        "Date Posted", "Valid Through", "Submitted URL", "Views", "Bot Visits", "Googlebot Visited?"
    ]
    all_job_rows = [
        [
            j["jobId"], j["clientJobId"], j["title"], j["location"], j["status"], str(j["isActive"]),
            format_date(j["datePosted"]), format_date(j["validThrough"]), j["submittedUrl"],
            j["views"], j["bot_visits"], j["has_bot"]
        ]
        for j in posted_all_jobs
    ]
    style_worksheet(ws_all, f"{client_name} - All Active Posted Jobs Detail (Total: {len(all_job_rows)})", all_job_headers, all_job_rows)

    # Save files
    filename = f"{filename_slug}_Views_and_No_Bot_Analysis.xlsx"
    target_dirs = [
        r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935",
        r"C:\Users\JOBIAK\Documents\Python",
        r"C:\Users\JOBIAK\Downloads"
    ]
    
    saved_paths = []
    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
        file_path = os.path.join(d, filename)
        try:
            wb.save(file_path)
            logger.info(f"Successfully saved to {file_path}")
            saved_paths.append(file_path)
        except PermissionError:
            fallback = os.path.join(d, f"{filename_slug}_Views_and_No_Bot_Analysis_Updated.xlsx")
            wb.save(fallback)
            logger.warning(f"File locked, saved fallback to {fallback}")
            saved_paths.append(fallback)

    return {
        "client": client_name,
        "emp_id": emp_id,
        "total_jobs": len(jobs),
        "posted_jobs": total_posted,
        "jobs_with_bot": total_with_bot,
        "jobs_no_bot": total_no_bot,
        "total_views": sum(google_views_map.values()),
        "bot_visits": sum(bot_visits_map.values()),
        "saved_paths": saved_paths
    }

def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI is missing from .env")

    primary_client = MongoClient(mongo_uri)
    creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
    if not creds:
        raise ValueError("prod_jobiak_ai creds not found")

    prod_client = MongoClient(creds["mongo_uri"])
    db = prod_client["prod_jobiak_ai"]

    targets = [
        ("YES! Communities", "6a86c3d7060e8f0b78b0dc66", "YES_Communities"),
        ("QRM", "6a7b516d060e8f0b78b0dc5a", "QRM")
    ]

    results = []
    for client_name, emp_id, slug in targets:
        res = generate_report_for_client(db, client_name, emp_id, slug)
        results.append(res)

    print("\n" + "="*60)
    print("ALL REPORTS GENERATED SUCCESSFULLY:")
    for r in results:
        print(f"Client: {r['client']} ({r['emp_id']})")
        print(f"  Total Jobs: {r['total_jobs']}")
        print(f"  Active Posted Jobs: {r['posted_jobs']}")
        print(f"  Posted Jobs with Bot: {r['jobs_with_bot']}")
        print(f"  Posted Jobs with NO Bot: {r['jobs_no_bot']}")
        print(f"  Total Google Views: {r['total_views']}")
        print(f"  Total Bot Visits: {r['bot_visits']}")
        print(f"  Saved Files: {r['saved_paths']}")
        print("-" * 60)

if __name__ == "__main__":
    main()
