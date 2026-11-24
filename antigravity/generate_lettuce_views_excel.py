"""
Lettuce Entertain You (Subdomain / Direct Apply) Google Jobs Views and Googlebot Analysis Generator
====================================================================================================
Generates a multi-tab formatted Excel workbook analyzing:
1. Executive Overview
2. Title Wise Performance (Views/Clicks & Bot Visits)
3. Location Wise Performance
4. Title + Location Combination Analysis
5. Active Posted Jobs With NO Googlebot Visit
6. All Active Posted Jobs Detail
7. Status & Lifecycle Breakdown (gpost & job_status)

Database: directclients_prod
Collections: Target_P4_Opt, userAnalytics
Client: Lettuce Entertain You (employerId: 'emp-jbk-lettuce')
"""

import os
import sys
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
logger = logging.getLogger("lettuce_excel_generator")


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

    # Title banner at Row 1
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=title_text)
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1B365D")
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    # Table Header row at Row 3
    ws.row_dimensions[3].height = 24
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Track column widths based on headers and sample data
    col_widths = {col_idx: len(str(h)) for col_idx, h in enumerate(headers, 1)}

    # Data rows starting at Row 4
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

            # Sample first 120 rows for auto width
            if row_idx <= 124:
                val_len = len(str(val or ""))
                if val_len > col_widths[col_idx]:
                    col_widths[col_idx] = val_len

    # Set column dimensions
    for col_idx, max_len in col_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 58)

    ws.freeze_panes = "A4"


def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI is missing from .env")

    logger.info("Connecting to central MongoDB registry...")
    primary_client = MongoClient(mongo_uri)
    creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "directclients_prod"})
    if not creds:
        raise ValueError("directclients_prod credentials not found in mongo_creds.creds")

    dc_client = MongoClient(creds.get("mongo_uri") or creds.get("uri"))
    db = dc_client["directclients_prod"]

    emp_id = "emp-jbk-lettuce"
    client_name = "Lettuce Entertain You"
    filename_slug = "Lettuce"

    jobs_col = db["Target_P4_Opt"]
    analytics_col = db["userAnalytics"]

    logger.info(f"Fetching jobs from directclients_prod.Target_P4_Opt for {emp_id}...")
    projection = {
        "_id": 1,
        "jobPubJobId": 1,
        "jobtitle": 1,
        "cleansedTitle": 1,
        "location": 1,
        "gpost": 1,
        "job_status": 1,
        "action": 1,
        "gpost_date": 1,
        "pub_expired": 1,
        "submittedUrl": 1,
        "url": 1
    }
    jobs = list(jobs_col.find({"employerId": emp_id}, projection))
    logger.info(f"Loaded {len(jobs)} total jobs for {client_name}.")

    logger.info("Aggregating Google organic views/clicks (isFromGoogle: True, isBot: False)...")
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
        {"$group": {"_id": "$jobPubJobId", "views": {"$sum": 1}}}
    ]
    google_views_map = {
        str(r["_id"]): r["views"]
        for r in analytics_col.aggregate(p_gviews, allowDiskUse=True)
        if r.get("_id")
    }
    logger.info(f"Google views aggregated: {sum(google_views_map.values())} views across {len(google_views_map)} jobs.")

    logger.info("Aggregating Googlebot visits (isBot: True)...")
    p_bot = [
        {"$match": {"employerId": emp_id, "isBot": True}},
        {"$group": {"_id": "$jobPubJobId", "visits": {"$sum": 1}}}
    ]
    bot_visits_map = {
        str(r["_id"]): r["visits"]
        for r in analytics_col.aggregate(p_bot, allowDiskUse=True)
        if r.get("_id")
    }
    logger.info(f"Googlebot visits aggregated: {sum(bot_visits_map.values())} visits across {len(bot_visits_map)} jobs.")

    logger.info("Enriching job records...")
    enriched_jobs = []
    gpost_status_counts = defaultdict(int)
    job_status_counts = defaultdict(int)

    for j in jobs:
        # Match using jobPubJobId or string of _id
        job_pub_id = str(j.get("jobPubJobId") or j.get("_id") or "").strip()
        v_count = google_views_map.get(job_pub_id, 0)
        b_visits = bot_visits_map.get(job_pub_id, 0)
        has_bot = "Yes" if b_visits > 0 else "No"

        title = (j.get("jobtitle") or j.get("cleansedTitle") or "Unknown").strip()
        location = (j.get("location") or "Unknown").strip()

        gpost = j.get("gpost")
        j_status = j.get("job_status")
        gpost_status_counts[gpost] += 1
        job_status_counts[j_status] += 1

        # Active posted on Google definition for Direct Apply:
        # gpost == 5 and job_status != 3
        is_posted = (gpost == 5 and j_status != 3)

        submitted_url = str(j.get("submittedUrl") or j.get("url") or "").strip()

        enriched_jobs.append({
            "jobPubJobId": job_pub_id,
            "title": title,
            "location": location,
            "gpost": gpost,
            "job_status": j_status,
            "action": str(j.get("action") or "").strip(),
            "gpost_date": j.get("gpost_date"),
            "pub_expired": j.get("pub_expired"),
            "submittedUrl": submitted_url,
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

    # Filter: Posted Jobs With No Bot
    posted_no_bot_jobs = [
        ej for ej in enriched_jobs
        if ej["is_posted"] and ej["bot_visits"] == 0
    ]
    posted_no_bot_jobs.sort(key=lambda x: (x["views"], str(x["gpost_date"] or "")), reverse=True)

    # Filter: All active posted jobs
    posted_all_jobs = [ej for ej in enriched_jobs if ej["is_posted"]]
    posted_all_jobs.sort(key=lambda x: (x["views"], str(x["gpost_date"] or "")), reverse=True)

    logger.info("Building Excel workbook...")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ---------------- TAB 1: EXECUTIVE OVERVIEW ----------------
    ws_summary = wb.create_sheet(title=f"{client_name[:25]} Overview")
    total_posted = len(posted_all_jobs)
    total_no_bot = len(posted_no_bot_jobs)
    total_with_bot = total_posted - total_no_bot
    bot_coverage_pct = f"{(total_with_bot / total_posted * 100):.1f}%" if total_posted > 0 else "0%"

    summary_headers = ["Metric", "Value", "Description / Definition"]
    summary_rows = [
        ["Employer ID", emp_id, f"Client unique identifier in directclients_prod"],
        ["Company Name", client_name, "Lettuce Entertain You Restaurants"],
        ["Architecture Type", "Direct Apply / Subdomain", "Hosted on directclients_prod (Target_P4_Opt)"],
        ["Subdomain URL", "https://gfj.lettuce.com", "Career site subdomain submitting Google Jobs feeds"],
        ["Total Jobs in Database", len(jobs), "All Lettuce job documents in Target_P4_Opt"],
        ["Active Posted Jobs on Google", total_posted, "Jobs live on Google (gpost == 5 and job_status != 3)"],
        ["Posted Jobs WITH Googlebot Visits", total_with_bot, "Active posted jobs crawled by Googlebot"],
        ["Posted Jobs with NO Googlebot Visit", total_no_bot, "Active posted jobs with 0 crawler visits"],
        ["Googlebot Crawl Coverage %", bot_coverage_pct, "Percentage of live jobs visited by Googlebot"],
        ["Jobs in 'To Post' State (gpost: 1)", gpost_status_counts.get(1, 0), "Jobs ready for Google Indexing API submission"],
        ["Jobs in 'Posting Queue' (gpost: 3)", gpost_status_counts.get(3, 0), "Jobs actively queued in posting pipeline"],
        ["Jobs in 'Expired' State (gpost: 6)", gpost_status_counts.get(6, 0), "Jobs removed/de-indexed from Google Search"],
        ["Feed Expired Jobs (job_status: 3)", job_status_counts.get(3, 0), "Jobs removed from Lettuce ATS feed"],
        ["Total Google Views/Clicks (Human)", sum(google_views_map.values()), "Total qualifying organic search clicks (isBot=False, isFromGoogle=True)"],
        ["Total Googlebot Crawl Visits", sum(bot_visits_map.values()), "Total Googlebot indexing and audit crawls (isBot=True)"],
        ["Distinct Job Titles", len(title_agg), "Distinct job requisition titles"],
        ["Distinct Locations", len(loc_agg), "Distinct hiring locations across Lettuce jobs"],
        ["Report Generated At (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "Data aggregation snapshot timestamp"]
    ]
    style_worksheet(ws_summary, f"{client_name} - Executive Views & Googlebot Crawl Summary", summary_headers, summary_rows)

    # ---------------- TAB 2: TITLE WISE ----------------
    ws_title = wb.create_sheet(title="Title Wise Views")
    title_headers = [
        "Job Title", "Total Jobs", "Active Posted Jobs", "Jobs With Bot Visit",
        "Jobs With NO Bot Visit", "Views/Clicks", "Total Bot Visits"
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
        "Jobs With NO Bot Visit", "Views/Clicks", "Total Bot Visits"
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
        "Jobs With NO Bot Visit", "Views/Clicks", "Total Bot Visits"
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
        "JobPubJobId", "Job Title", "Location", "gpost Status", "job_status", "Action",
        "Date Posted", "Valid Through / Expiry", "Submitted URL", "Views/Clicks", "Bot Visits"
    ]
    nobot_job_rows = [
        [
            j["jobPubJobId"], j["title"], j["location"], j["gpost"], j["job_status"], j["action"],
            format_date(j["gpost_date"]), format_date(j["pub_expired"]), j["submittedUrl"],
            j["views"], j["bot_visits"]
        ]
        for j in posted_no_bot_jobs
    ]
    style_worksheet(ws_nobot, f"{client_name} - Active Posted Jobs With NO Googlebot Visit (Total: {len(nobot_job_rows)})", nobot_job_headers, nobot_job_rows)

    # ---------------- TAB 6: ALL ACTIVE POSTED JOBS ----------------
    ws_all = wb.create_sheet(title="All Active Posted Jobs")
    all_job_headers = [
        "JobPubJobId", "Job Title", "Location", "gpost Status", "job_status", "Action",
        "Date Posted", "Valid Through / Expiry", "Submitted URL", "Views/Clicks", "Bot Visits", "Googlebot Visited?"
    ]
    all_job_rows = [
        [
            j["jobPubJobId"], j["title"], j["location"], j["gpost"], j["job_status"], j["action"],
            format_date(j["gpost_date"]), format_date(j["pub_expired"]), j["submittedUrl"],
            j["views"], j["bot_visits"], j["has_bot"]
        ]
        for j in posted_all_jobs
    ]
    style_worksheet(ws_all, f"{client_name} - All Active Posted Jobs Detail (Total: {len(all_job_rows)})", all_job_headers, all_job_rows)

    # ---------------- TAB 7: STATUS BREAKDOWN ----------------
    ws_status = wb.create_sheet(title="Status Breakdown")
    status_headers = ["gpost Status Code", "Status Meaning", "Total Jobs Count", "% of Total Jobs"]
    status_meanings = {
        1: "To Post (Ready for Google Indexing)",
        3: "Posting Queue (Queued in work pipeline)",
        4: "Post Fail (Google Indexing API failure)",
        5: "Posted (Actively Live on Google)",
        6: "Expired (De-indexed from Google)",
        8: "Expires Queue (Queued for de-indexing)"
    }
    status_rows = []
    total_all_jobs = len(jobs)
    for code, count in sorted(gpost_status_counts.items(), key=lambda x: str(x[0])):
        meaning = status_meanings.get(code, f"Status Code {code}")
        pct = f"{(count / total_all_jobs * 100):.1f}%" if total_all_jobs > 0 else "0%"
        status_rows.append([code, meaning, count, pct])

    style_worksheet(ws_status, f"{client_name} - Lifecycle Status Code Distribution", status_headers, status_rows)

    # Save to disk
    filename = f"{filename_slug}_Views_and_No_Bot_Analysis.xlsx"
    target_dirs = [
        r"C:\Users\JOBIAK\Documents\Python",
        r"C:\Users\JOBIAK\Downloads",
        r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
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

    print("\n" + "="*60)
    print(f"LETTUCE ENTERTAIN YOU REPORT GENERATED SUCCESSFULLY:")
    print(f"  Total Jobs in DB: {len(jobs)}")
    print(f"  Active Posted Jobs (gpost=5, job_status!=3): {total_posted}")
    print(f"  Posted Jobs with Bot Visits: {total_with_bot}")
    print(f"  Posted Jobs with NO Bot Visit: {total_no_bot}")
    print(f"  Googlebot Crawl Coverage: {bot_coverage_pct}")
    print(f"  Total Pure Human Google Views/Clicks: {sum(google_views_map.values())}")
    print(f"  Total Googlebot Visits: {sum(bot_visits_map.values())}")
    print(f"  Saved File Paths: {saved_paths}")
    print("="*60)


if __name__ == "__main__":
    main()
