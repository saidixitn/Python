"""
Year-Wise Multi-Worker Domain Views & Clicks Reporting Engine (From Day 1)
==========================================================================
- Runs 1 dedicated worker per calendar year (2023, 2024, 2025, 2026) concurrently.
- Extracts daily & monthly pure human Google views (isBot=False, isFromGoogle=True,
  browserType != 'Unknown', deviceType != 'Unknown') from Day 1 to present.
- Computes all-time single-day Max Clicks (+ date), Yesterday (2026-11-11) Clicks,
  and Month-wise Views vertically.
- Updates Google Sheet tab 'Dixit', generates styled Excel (.xlsx), and exports CSVs.
"""

import os
import csv
import time
import logging
from datetime import datetime, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pymongo import MongoClient
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import gspread

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("YearWiseDay1Reporter")

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found in .env")

ROOT_CLIENT = MongoClient(MONGO_URI, maxPoolSize=50)
CREDS_COL = ROOT_CLIENT["mongo_creds"]["creds"]

PROD_CRED = CREDS_COL.find_one({"domain": "prod_jobiak_ai"})
DC_CRED = CREDS_COL.find_one({"domain": "directclients_prod"})

PROD_CLIENT = MongoClient(PROD_CRED.get("mongo_uri") or PROD_CRED.get("uri"), maxPoolSize=50)
DC_CLIENT = MongoClient(DC_CRED.get("mongo_uri") or DC_CRED.get("uri"), maxPoolSize=50)

PROD_DB = PROD_CLIENT["prod_jobiak_ai"]
DC_DB = DC_CLIENT["directclients_prod"]
OLDSTATS_COL = ROOT_CLIENT["daily_stats"]["oldstats"]
OUTPUT_COL = ROOT_CLIENT["daily_stats"]["output"]

DOMAINS_CONFIG = [
    {"lead": "Dixit", "domain": "qrmhealth.com/gfj/", "domain_type": "Proxy", "employerId": "6a7b516d060e8f0b78b0dc5a", "client": "Quality Rehab Management (QRM)"},
    {"lead": "Dixit", "domain": "championwindow.com/gfj/", "domain_type": "Proxy", "employerId": "5f16b7fba780b2085c230ea1", "client": "Champion Window"},
    {"lead": "Dixit", "domain": "imperialsupplies.com/jobiak", "domain_type": "Proxy", "employerId": "5e6f1017a780b23e130a1c3b", "client": "Imperial Supplies"},
    {"lead": "Dixit", "domain": "gfj.cooperfarms.com/", "domain_type": "Direct Apply", "employerId": "emp-jbk-cooperfarms", "client": "Cooper Farms"},
    {"lead": "Dixit", "domain": "gfj.virtahealth.com/", "domain_type": "Direct Apply", "employerId": "emp-jbk-virtahealth", "client": "Virta Health"},
    {"lead": "Dixit", "domain": "gfj.lettuce.com", "domain_type": "Direct Apply", "employerId": "emp-jbk-lettuce", "client": "Lettuce Entertain You"},
    {"lead": "Dixit", "domain": "yescommunities.com/gfj/", "domain_type": "Proxy", "employerId": "6a86c3d7060e8f0b78b0dc66", "client": "YES! Communities"},
    {"lead": "Dixit", "domain": "concentrix.com/gfj/", "domain_type": "Proxy", "employerId": "6a8871d1060e8f0b78b0dc69", "client": "Concentrix"},
    {"lead": "Dixit", "domain": "hcsgcorp.com/gfj/", "domain_type": "Proxy", "employerId": "6a904f26060e8f0b78b0dc81", "client": "Healthcare Services Group (HCSG)"},
    {"lead": "Dixit", "domain": "abskids.com/gfj/", "domain_type": "Proxy", "employerId": "6aa8d214060e8f0b78b0dc87", "client": "ABS Kids"},
    {"lead": "Dixit", "domain": "suncrestcare.com/gfj/", "domain_type": "Proxy", "employerId": "6ad8dd02060e8f0b78b0dc9a", "client": "Suncrest Care"},
]


def _agg_daily_for_emp_year(col, emp_id: str, start_dt: datetime, end_dt: datetime):
    """Aggregate daily views for a single employer within a specific year window."""
    pipeline = [
        {
            "$match": {
                "employerId": emp_id,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$gte": start_dt, "$lt": end_dt}
            }
        },
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}},
                "views": {"$sum": 1}
            }
        }
    ]
    return {
        r["_id"]: r["views"]
        for r in col.aggregate(pipeline, allowDiskUse=True)
        if r.get("_id")
    }


def year_worker(year: int):
    """
    1 dedicated worker per calendar year.
    Fetches daily views for all 11 employers for that year.
    """
    t0 = time.time()
    logger.info(f"[Worker-{year}] Started processing year {year}...")
    start_dt = datetime(year, 1, 1, 0, 0, 0)
    end_dt = datetime(year + 1, 1, 1, 0, 0, 0)

    year_daily = defaultdict(dict)  # emp -> {YYYY-MM-DD: views}

    if year == 2026:
        # Fast path for Aug-Nov 2026 using pre-aggregated daily_stats (oldstats + output)
        for item in DOMAINS_CONFIG:
            emp = item["employerId"]
            for doc in OLDSTATS_COL.find({"employerId": emp}):
                dt = doc.get("Date")
                if dt and dt.year == 2026:
                    year_daily[emp][dt.strftime("%Y-%m-%d")] = doc.get("DB_Clicks", 0)
            for doc in OUTPUT_COL.find({"employerId": emp}):
                dt = doc.get("Date")
                if dt and dt.year == 2026 and "DB_Clicks" in doc:
                    year_daily[emp][dt.strftime("%Y-%m-%d")] = doc.get("DB_Clicks", 0)

        # Fetch Jan-Jul 2026 for employers that were live before Aug 2026
        # (Imperial Supplies for Proxy; Cooper Farms, Virta Health, Lettuce for Direct Apply)
        jan_aug_end = datetime(2026, 8, 1, 0, 0, 0)
        pre_aug_targets = [
            (PROD_DB["userAnalytics"], "5e6f1017a780b23e130a1c3b"),  # Imperial
            (DC_DB["userAnalytics"], "emp-jbk-cooperfarms"),
            (DC_DB["userAnalytics"], "emp-jbk-virtahealth"),
            (DC_DB["userAnalytics"], "emp-jbk-lettuce"),
        ]
        for col, emp in pre_aug_targets:
            res = _agg_daily_for_emp_year(col, emp, start_dt, jan_aug_end)
            for d_str, v in res.items():
                year_daily[emp][d_str] = v

        # Ensure Cooper Farms & Virta Health also have Aug-Nov 2026 from DC_DB
        aug_start = datetime(2026, 8, 1, 0, 0, 0)
        for emp in ["emp-jbk-cooperfarms", "emp-jbk-virtahealth"]:
            res = _agg_daily_for_emp_year(DC_DB["userAnalytics"], emp, aug_start, end_dt)
            for d_str, v in res.items():
                year_daily[emp][d_str] = v
    else:
        # Historical years (2023, 2024, 2025): query userAnalytics for active historical employers
        # Check Imperial Supplies (active since Mar 2023)
        res_imp = _agg_daily_for_emp_year(PROD_DB["userAnalytics"], "5e6f1017a780b23e130a1c3b", start_dt, end_dt)
        if res_imp:
            year_daily["5e6f1017a780b23e130a1c3b"].update(res_imp)

    logger.info(f"[Worker-{year}] Finished in {time.time() - t0:.2f}s.")
    return year, year_daily


def main():
    t_start = time.time()
    years = [2023, 2024, 2025, 2026]
    logger.info(f"Launching 1 worker per year concurrently for {years}...")

    all_daily_views = defaultdict(dict)  # emp -> {YYYY-MM-DD: views}

    with ThreadPoolExecutor(max_workers=len(years)) as executor:
        futures = [executor.submit(year_worker, y) for y in years]
        for fut in as_completed(futures):
            year, y_daily = fut.result()
            for emp, d_map in y_daily.items():
                all_daily_views[emp].update(d_map)

    # Roll up daily views into monthly views per employer
    monthly_views = defaultdict(lambda: defaultdict(int))  # emp -> {YYYY-MM: views}
    for emp, d_map in all_daily_views.items():
        for d_str, v in d_map.items():
            m_str = d_str[:7]
            monthly_views[emp][m_str] += v

    yesterday_str = "2026-11-11"

    # 1. Build Vertical Summary Rows (Max Clicks & Yesterday)
    summary_rows = []
    for item in DOMAINS_CONFIG:
        emp = item["employerId"]
        d_map = all_daily_views.get(emp, {})

        if d_map:
            max_d_str, max_c = max(d_map.items(), key=lambda x: x[1])
        else:
            max_d_str, max_c = ("N/A", 0)

        yesterday_clicks = d_map.get(yesterday_str, 0)
        total_v = sum(monthly_views[emp].values())

        summary_rows.append({
            "Lead": item["lead"],
            "Client": item["client"],
            "Domain": item["domain"],
            "Domain Type": item["domain_type"],
            "EmployerId": emp,
            "Max Clicks (Single Day)": max_c,
            "Max Clicks Date": max_d_str,
            "Yesterday Clicks (2026-11-11)": yesterday_clicks,
            "Total Views (Day 1 - Present)": total_v
        })

    # 2. Build Vertical Monthly Breakdown Rows (Client, EmployerId, Year, Month, Views)
    monthly_rows = []
    for item in DOMAINS_CONFIG:
        emp = item["employerId"]
        emp_months = sorted(monthly_views[emp].keys())
        for m_str in emp_months:
            v = monthly_views[emp][m_str]
            y, mon = m_str.split("-")
            monthly_rows.append({
                "Lead": item["lead"],
                "Client": item["client"],
                "Domain": item["domain"],
                "Domain Type": item["domain_type"],
                "EmployerId": emp,
                "Year": int(y),
                "Month": int(mon),
                "Year-Month": m_str,
                "Views": v
            })

    # -------------------------------------------------------------
    # EXPORT 1: CSV FILES
    # -------------------------------------------------------------
    csv_summary_path = r"C:\Users\JOBIAK\Documents\Python\domain_max_and_yesterday_clicks.csv"
    with open(csv_summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    csv_monthly_path = r"C:\Users\JOBIAK\Documents\Python\monthly_views_from_day_1.csv"
    with open(csv_monthly_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(monthly_rows[0].keys()))
        writer.writeheader()
        writer.writerows(monthly_rows)

    logger.info(f"Saved CSVs: {csv_summary_path} and {csv_monthly_path}")

    # -------------------------------------------------------------
    # EXPORT 2: STYLED EXCEL WORKBOOK (.xlsx) - VERTICAL LAYOUT
    # -------------------------------------------------------------
    excel_path = r"C:\Users\JOBIAK\Documents\Python\Domain_Views_Monthly_and_Max_Report.xlsx"
    wb = openpyxl.Workbook()

    f_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    f_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_data = Font(name="Calibri", size=11)

    fill_navy = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    fill_blue = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9")
    )

    def write_styled_sheet(ws, title_text, rows_list):
        ws.views.sheetView[0].showGridLines = True
        headers = list(rows_list[0].keys())
        col_count = len(headers)

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
        t_cell = ws.cell(row=1, column=1, value=title_text)
        t_cell.font = f_title
        t_cell.fill = fill_navy
        t_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 34

        ws.append([])
        ws.append(headers)
        ws.row_dimensions[3].height = 24
        for c_idx in range(1, col_count + 1):
            c = ws.cell(row=3, column=c_idx)
            c.font = f_header
            c.fill = fill_blue
            c.alignment = Alignment(horizontal="center", vertical="center")

        for r_idx, row_dict in enumerate(rows_list, 4):
            ws.row_dimensions[r_idx].height = 20
            vals = list(row_dict.values())
            ws.append(vals)
            for c_idx, val in enumerate(vals, 1):
                c = ws.cell(row=r_idx, column=c_idx)
                c.font = f_data
                c.border = thin_border
                if r_idx % 2 == 0:
                    c.fill = fill_zebra
                if isinstance(val, (int, float)):
                    if headers[c_idx - 1] in ("Year", "Month"):
                        c.number_format = "0"
                    else:
                        c.number_format = "#,##0"
                    c.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 4, 12)

    ws1 = wb.active
    ws1.title = "Domain Summary"
    write_styled_sheet(ws1, "Lead: Dixit - Domain Summary (Max Clicks & Yesterday)", summary_rows)

    ws2 = wb.create_sheet(title="Monthly Views (Vertical)")
    write_styled_sheet(ws2, "Lead: Dixit - Monthly Views From Day 1 (Vertical)", monthly_rows)

    wb.save(excel_path)
    logger.info(f"Saved Excel Report: {excel_path}")

    # -------------------------------------------------------------
    # EXPORT 3: GOOGLE SHEETS ('Dixit' Tab - Vertical Layout)
    # -------------------------------------------------------------
    logger.info("Updating Google Sheet 'Dixit' (Vertical Layout)...")
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key("1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds")

    try:
        ws_dixit = sh.worksheet("Dixit")
        ws_dixit.clear()
    except gspread.exceptions.WorksheetNotFound:
        ws_dixit = sh.add_worksheet(title="Dixit", rows=500, cols=15)

    headers_s = list(summary_rows[0].keys())
    headers_m = list(monthly_rows[0].keys())

    sheet_data = [
        ["LEAD: DIXIT - DOMAIN VIEWS & CLICKS REPORT (FROM DAY 1)"],
        [f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"],
        [],
        ["SECTION 1: DOMAIN PERFORMANCE SUMMARY (MAX CLICKS & YESTERDAY)"],
        headers_s
    ]
    for s in summary_rows:
        sheet_data.append(list(s.values()))

    sec2_header_row_idx = len(sheet_data) + 3  # 0-based index for formatting
    sheet_data.append([])
    sheet_data.append([])
    sheet_data.append(["SECTION 2: MONTHLY VIEWS FROM DAY 1 (VERTICAL)"])
    sheet_data.append(headers_m)
    for m in monthly_rows:
        sheet_data.append(list(m.values()))

    ws_dixit.update(sheet_data, "A1")

    # Style headers in Google Sheets
    sh.batch_update({
        "requests": [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws_dixit.id,
                        "startRowIndex": 4,
                        "endRowIndex": 5,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers_s)
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)"
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": ws_dixit.id,
                        "startRowIndex": sec2_header_row_idx,
                        "endRowIndex": sec2_header_row_idx + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers_m)
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat)"
                }
            }
        ]
    })
    logger.info("Google Sheet 'Dixit' updated successfully!")

    # Copy to Downloads & Artifacts
    target_dirs = [
        r"C:\Users\JOBIAK\Downloads",
        r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
    ]
    for d in target_dirs:
        os.makedirs(d, exist_ok=True)
        for src in [csv_summary_path, csv_monthly_path, excel_path]:
            dst = os.path.join(d, os.path.basename(src))
            try:
                with open(src, "rb") as sf, open(dst, "wb") as df:
                    df.write(sf.read())
            except Exception:
                pass

    print("\n" + "=" * 75)
    print(f"COMPLETED IN {time.time() - t_start:.2f}s (1 WORKER PER YEAR: {years})")
    print(f"  Google Sheet Tab: Dixit -> https://docs.google.com/spreadsheets/d/1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds/edit#gid={ws_dixit.id}")
    print(f"  Excel Report:     {excel_path}")
    print(f"  Summary CSV:      {csv_summary_path}")
    print(f"  Monthly CSV:      {csv_monthly_path}")
    print("=" * 75)


if __name__ == "__main__":
    main()
