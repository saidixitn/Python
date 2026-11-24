"""
Master All-Leads Domain Views & Clicks Reporting Engine (Fast & Incremental)
==========================================================================
1. Reads all 44 clients dynamically from the 'Domains' tab in Google Sheets.
2. Processes Direct Apply (directclients_prod) and Proxy (prod_jobiak_ai)
   with cluster-safe concurrency (5 workers DC, 4 workers Proxy) + hint='employerId_1'
   to avoid MongoDB I/O saturation.
3. Saves each Lead incrementally to MongoDB 'dc_prod' AND updates each Lead's
   Google Sheet tab ('Dixit', 'Tarun', 'Hari Prasad', 'Hari_Uva') immediately
   as soon as that Lead's domains finish.
4. Exports styled Excel workbook (.xlsx) and CSV files.
"""

import os
import csv
import time
import threading
import logging
from datetime import datetime, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import gspread

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("AllLeadsFast")

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI not found in .env")

SPREADSHEET_ID = "1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds"
YESTERDAY_STR = "2026-11-11"

ROOT_CLIENT = MongoClient(MONGO_URI, maxPoolSize=50)
CREDS_COL = ROOT_CLIENT["mongo_creds"]["creds"]

PROD_CRED = CREDS_COL.find_one({"domain": "prod_jobiak_ai"})
DC_CRED = CREDS_COL.find_one({"domain": "directclients_prod"})

PROD_CLIENT = MongoClient(PROD_CRED.get("mongo_uri") or PROD_CRED.get("uri"), maxPoolSize=30)
DC_CLIENT = MongoClient(DC_CRED.get("mongo_uri") or DC_CRED.get("uri"), maxPoolSize=30)

PROD_DB = PROD_CLIENT["prod_jobiak_ai"]
DC_DB = DC_CLIENT["directclients_prod"]
DC_PROD_DB = ROOT_CLIENT["dc_prod"]
OLDSTATS_COL = ROOT_CLIENT["daily_stats"]["oldstats"]
OUTPUT_COL = ROOT_CLIENT["daily_stats"]["output"]

# Employers already verified to have 0 qualifying Google human views before 2026-08-01
# (so daily_stats oldstats+output gives their 100% Day-1 history in <0.1s)
DAILY_STATS_ONLY_EMPS = {
    "6a7b516d060e8f0b78b0dc5a",  # qrmhealth
    "5f16b7fba780b2085c230ea1",  # championwindow
    "6a86c3d7060e8f0b78b0dc66",  # yescommunities
    "6a8871d1060e8f0b78b0dc69",  # concentrix
    "6a904f26060e8f0b78b0dc81",  # hcsgcorp
    "6aa8d214060e8f0b78b0dc87",  # abskids
    "6ad8dd02060e8f0b78b0dc9a",  # suncrestcare
}

GSHEET_LOCK = threading.Lock()


def fetch_domains_from_sheet():
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet("Domains")
    rows = ws.get_all_values()
    domains = []
    for r in rows[1:]:
        if len(r) < 4 or not r[3].strip():
            continue
        domains.append({
            "lead": r[0].strip(),
            "domain": r[1].strip(),
            "domain_type": r[2].strip(),
            "employerId": r[3].strip(),
        })
    logger.info(f"Loaded {len(domains)} clients from 'Domains' sheet.")
    return domains, sh


def process_employer(item: dict):
    emp_id = item["employerId"]
    dtype = item["domain_type"]
    t0 = time.time()

    # Fast path if employer is in DAILY_STATS_ONLY_EMPS
    if emp_id in DAILY_STATS_ONLY_EMPS:
        daily_map = {}
        for doc in OLDSTATS_COL.find({"employerId": emp_id}):
            dt = doc.get("Date")
            if dt:
                daily_map[dt.strftime("%Y-%m-%d")] = doc.get("DB_Clicks", 0)
        for doc in OUTPUT_COL.find({"employerId": emp_id}):
            dt = doc.get("Date")
            if dt and "DB_Clicks" in doc:
                daily_map[dt.strftime("%Y-%m-%d")] = doc.get("DB_Clicks", 0)
        logger.info(f"  [Fast] [{item['lead']}] {item['domain']}: {sum(daily_map.values())} views ({len(daily_map)} days) in {time.time()-t0:.2f}s")
        return item, daily_map

    col = PROD_DB["userAnalytics"] if dtype == "Proxy" else DC_DB["userAnalytics"]
    pipeline = [
        {
            "$match": {
                "employerId": emp_id,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$type": "date"}
            }
        },
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}},
                "views": {"$sum": 1}
            }
        }
    ]
    try:
        daily_map = {
            r["_id"]: r["views"]
            for r in col.aggregate(pipeline, allowDiskUse=True, hint="employerId_1")
            if r.get("_id")
        }
        elapsed = time.time() - t0
        logger.info(f"  Done [{item['lead']}] {item['domain']} ({emp_id}): {sum(daily_map.values())} views ({len(daily_map)} days) in {elapsed:.1f}s")
        return item, daily_map
    except Exception as e:
        logger.error(f"  Error [{item['lead']}] {item['domain']} ({emp_id}): {e}")
        return item, {}


def build_rows_for_items(items: list, daily_views_map: dict):
    summary_rows = []
    monthly_rows = []
    for item in items:
        emp = item["employerId"]
        d_map = daily_views_map.get(emp, {})

        if d_map:
            max_d_str, max_c = max(d_map.items(), key=lambda x: x[1])
        else:
            max_d_str, max_c = ("N/A", 0)

        yesterday_clicks = d_map.get(YESTERDAY_STR, 0)

        m_totals = defaultdict(int)
        for d_str, v in d_map.items():
            m_totals[d_str[:7]] += v

        total_v = sum(m_totals.values())
        summary_rows.append({
            "Lead": item["lead"],
            "Domain": item["domain"],
            "Domain Type": item["domain_type"],
            "EmployerId": emp,
            "Max Clicks (Single Day)": max_c,
            "Max Clicks Date": max_d_str,
            f"Yesterday Clicks ({YESTERDAY_STR})": yesterday_clicks,
            "Total Views (Day 1 - Present)": total_v
        })

        for m_str in sorted(m_totals.keys()):
            y, mon = m_str.split("-")
            monthly_rows.append({
                "Lead": item["lead"],
                "Domain": item["domain"],
                "Domain Type": item["domain_type"],
                "EmployerId": emp,
                "Year": int(y),
                "Month": int(mon),
                "Year-Month": m_str,
                "Views": m_totals[m_str]
            })
    return summary_rows, monthly_rows


def save_to_dc_prod(summary_rows: list, monthly_rows: list):
    now_utc = datetime.now(timezone.utc)

    summary_col = DC_PROD_DB["domain_summary"]
    summary_col.create_index("employerId", unique=True)
    ops_s = [
        UpdateOne(
            {"employerId": s["EmployerId"]},
            {"$set": {
                "lead": s["Lead"],
                "domain": s["Domain"],
                "domainType": s["Domain Type"],
                "employerId": s["EmployerId"],
                "maxClicks": s["Max Clicks (Single Day)"],
                "maxClicksDate": s["Max Clicks Date"],
                "yesterdayClicks": s[f"Yesterday Clicks ({YESTERDAY_STR})"],
                "totalViews": s["Total Views (Day 1 - Present)"],
                "updatedAt": now_utc
            }},
            upsert=True
        )
        for s in summary_rows
    ]
    if ops_s:
        summary_col.bulk_write(ops_s, ordered=False)

    monthly_col = DC_PROD_DB["monthly_views"]
    monthly_col.create_index([("employerId", 1), ("yearMonth", 1)], unique=True)
    ops_m = [
        UpdateOne(
            {"employerId": m["EmployerId"], "yearMonth": m["Year-Month"]},
            {"$set": {
                "lead": m["Lead"],
                "domain": m["Domain"],
                "domainType": m["Domain Type"],
                "employerId": m["EmployerId"],
                "year": m["Year"],
                "month": m["Month"],
                "yearMonth": m["Year-Month"],
                "views": m["Views"],
                "updatedAt": now_utc
            }},
            upsert=True
        )
        for m in monthly_rows
    ]
    if ops_m:
        monthly_col.bulk_write(ops_m, ordered=False)


def push_lead_to_google_sheet(sh, lead: str, lead_summary: list, lead_monthly: list):
    with GSHEET_LOCK:
        headers_s = list(lead_summary[0].keys())
        headers_m = list(lead_monthly[0].keys()) if lead_monthly else ["Lead", "Domain", "Domain Type", "EmployerId", "Year", "Month", "Year-Month", "Views"]

        try:
            ws = sh.worksheet(lead)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=lead, rows=max(len(lead_monthly) + len(lead_summary) + 25, 200), cols=15)

        sheet_data = [
            [f"LEAD: {lead.upper()} - DOMAIN VIEWS & CLICKS REPORT (FROM DAY 1)"],
            [f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"],
            [],
            ["SECTION 1: DOMAIN PERFORMANCE SUMMARY (MAX CLICKS & YESTERDAY)"],
            headers_s
        ]
        for s in lead_summary:
            sheet_data.append(list(s.values()))

        sec2_header_idx = len(sheet_data) + 3
        sheet_data.append([])
        sheet_data.append([])
        sheet_data.append(["SECTION 2: MONTHLY VIEWS FROM DAY 1 (VERTICAL)"])
        sheet_data.append(headers_m)
        for m in lead_monthly:
            sheet_data.append(list(m.values()))

        ws.update(sheet_data, "A1")

        sh.batch_update({
            "requests": [
                {
                    "repeatCell": {
                        "range": {"sheetId": ws.id, "startRowIndex": 4, "endRowIndex": 5, "startColumnIndex": 0, "endColumnIndex": len(headers_s)},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"
                    }
                },
                {
                    "repeatCell": {
                        "range": {"sheetId": ws.id, "startRowIndex": sec2_header_idx, "endRowIndex": sec2_header_idx + 1, "startColumnIndex": 0, "endColumnIndex": len(headers_m)},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.59}, "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}}}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat)"
                    }
                }
            ]
        })
        logger.info(f"==> UPDATED GOOGLE SHEET TAB '{lead}' ({len(lead_summary)} domains, {len(lead_monthly)} monthly rows)!")


def export_excel_and_csv(domains_list: list, summary_rows: list, monthly_rows: list):
    csv_summary_path = r"C:\Users\JOBIAK\Documents\Python\all_domains_max_and_yesterday_clicks.csv"
    with open(csv_summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    csv_monthly_path = r"C:\Users\JOBIAK\Documents\Python\all_domains_monthly_views_vertical.csv"
    with open(csv_monthly_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(monthly_rows[0].keys()))
        writer.writeheader()
        writer.writerows(monthly_rows)

    excel_path = r"C:\Users\JOBIAK\Documents\Python\All_Leads_Domain_Views_Report.xlsx"
    wb = openpyxl.Workbook()

    f_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    f_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    f_data = Font(name="Calibri", size=11)
    fill_navy = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    fill_blue = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9")
    )

    def write_styled_sheet(ws, title_text, rows_list):
        ws.views.sheetView[0].showGridLines = True
        if not rows_list:
            return
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
                    c.number_format = "0" if headers[c_idx - 1] in ("Year", "Month") else "#,##0"
                    c.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left", vertical="center")

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 4, 12)

    ws1 = wb.active
    ws1.title = "All Domains Summary"
    write_styled_sheet(ws1, "All Leads - Domain Summary (Max Clicks & Yesterday)", summary_rows)

    ws2 = wb.create_sheet(title="All Monthly Views (Vertical)")
    write_styled_sheet(ws2, "All Leads - Monthly Views From Day 1 (Vertical)", monthly_rows)

    leads = list(dict.fromkeys(d["lead"] for d in domains_list))
    for lead in leads:
        lead_s = [s for s in summary_rows if s["Lead"] == lead]
        ws_l = wb.create_sheet(title=f"{lead[:25]} Summary")
        write_styled_sheet(ws_l, f"Lead: {lead} - Domain Summary", lead_s)

    wb.save(excel_path)
    for d in [r"C:\Users\JOBIAK\Downloads", r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"]:
        os.makedirs(d, exist_ok=True)
        for src in [csv_summary_path, csv_monthly_path, excel_path]:
            dst = os.path.join(d, os.path.basename(src))
            try:
                with open(src, "rb") as sf, open(dst, "wb") as df:
                    df.write(sf.read())
            except Exception:
                pass
    return csv_summary_path, csv_monthly_path, excel_path


def main():
    t_start = time.time()
    domains_list, sh = fetch_domains_from_sheet()

    # Group domains by Lead so we can update Google Sheet + dc_prod as soon as each Lead finishes
    lead_groups = defaultdict(list)
    for d in domains_list:
        lead_groups[d["lead"]].append(d)

    daily_views_map = {}
    lead_done_counts = defaultdict(int)
    pushed_leads = set()
    lock = threading.Lock()

    def handle_completion(item, daily_map):
        lead = item["lead"]
        with lock:
            daily_views_map[item["employerId"]] = daily_map
            lead_done_counts[lead] += 1
            ready = (lead_done_counts[lead] == len(lead_groups[lead])) and (lead not in pushed_leads)
            if ready:
                pushed_leads.add(lead)

        if ready:
            l_items = lead_groups[lead]
            l_sum, l_mon = build_rows_for_items(l_items, daily_views_map)
            save_to_dc_prod(l_sum, l_mon)
            push_lead_to_google_sheet(sh, lead, l_sum, l_mon)

    dc_items = [d for d in domains_list if d["domain_type"] != "Proxy"]
    proxy_items = [d for d in domains_list if d["domain_type"] == "Proxy"]

    logger.info(f"Running {len(dc_items)} Direct Apply (5 workers) + {len(proxy_items)} Proxy (4 workers)...")
    with ThreadPoolExecutor(max_workers=5) as dc_pool, ThreadPoolExecutor(max_workers=4) as proxy_pool:
        futures = [dc_pool.submit(process_employer, it) for it in dc_items] + \
                  [proxy_pool.submit(process_employer, it) for it in proxy_items]
        for fut in as_completed(futures):
            it, d_map = fut.result()
            handle_completion(it, d_map)

    all_sum, all_mon = build_rows_for_items(domains_list, daily_views_map)
    csv_s, csv_m, xlsx_p = export_excel_and_csv(domains_list, all_sum, all_mon)

    print("\n" + "=" * 75)
    print(f"ALL {len(domains_list)} CLIENTS COMPLETED IN {time.time() - t_start:.2f}s!")
    print(f"  MongoDB Saved:  dc_prod.domain_summary & dc_prod.monthly_views")
    print(f"  Google Sheet:   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    print(f"  Excel Report:   {xlsx_p}")
    print(f"  Summary CSV:    {csv_s}")
    print(f"  Monthly CSV:    {csv_m}")
    print("=" * 75)


if __name__ == "__main__":
    main()
