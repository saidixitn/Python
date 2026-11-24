import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
pj_uri = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
pj_client = MongoClient(pj_uri)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"
print("Fetching all posted jobs for YES Communities...")
jobs = list(db.job.find(
    {"employerId": emp_id, "status": "posted"},
    {"jobId": 1, "title": 1, "location": 1, "description": 1, "datePosted": 1, "validThrough": 1, "clientJobId": 1, "submittedUrl": 1, "url": 1}
))
print(f"Total posted jobs: {len(jobs)}")

# Regex patterns
rx_posted_prefix = re.compile(r'^\s*(Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*', re.IGNORECASE)
rx_dot_prefix = re.compile(r'^\s*<p><strong>\s*\.\s*</strong></p>\s*', re.IGNORECASE)
rx_pay_block = re.compile(r'<p><strong>Pay Type:</strong>.*?</p>', re.DOTALL | re.IGNORECASE)

records = []
timestamp_records = []
stray_dot_records = []
careers_url_records = []
trailing_addr_records = []

for j in jobs:
    jid = j["jobId"]
    title = j.get("title", "")
    loc = j.get("location", "")
    desc = j.get("description", "")
    cid = j.get("clientJobId", "")
    url = j.get("submittedUrl") or j.get("url") or ""
    
    # 1. Posted timestamp
    m_posted = rx_posted_prefix.search(desc)
    has_posted_ts = bool(m_posted)
    posted_ts_str = m_posted.group(1).strip() if m_posted else ""
    
    # 2. Stray dot
    m_dot = rx_dot_prefix.search(desc)
    has_stray_dot = bool(m_dot)
    
    # 3. Careers URL / Anti-fraud
    has_careers_url = ("yescommunities.com/Careers" in desc) or ("yescommunities.com/careers" in desc)
    fraud_variant = ""
    if "your safety matters to us" in desc.lower():
        fraud_variant = "Safety / Scams Warning (visit yescommunities.com/careers/)"
    elif "fraudulent recruiting outreach" in desc.lower():
        fraud_variant = "Fraudulent Outreach Warning (https://www.yescommunities.com/Careers)"
        
    # 4. Trailing un-tagged address
    last_gt = desc.rfind('>')
    trailing_text = ""
    if last_gt != -1 and last_gt < len(desc) - 1:
        trailing_text = desc[last_gt+1:].strip()
    has_trailing_addr = bool(trailing_text)
    
    # 5. Pay type block
    has_pay_block = bool(rx_pay_block.search(desc))
    
    # Cleaned description preview
    cleaned_desc = desc
    if has_posted_ts:
        cleaned_desc = rx_posted_prefix.sub('', cleaned_desc)
    if has_stray_dot:
        cleaned_desc = rx_dot_prefix.sub('', cleaned_desc)
    if has_trailing_addr:
        cleaned_desc = cleaned_desc[:last_gt+1].strip()
        
    rec = {
        "jobId": jid,
        "title": title,
        "location": loc,
        "clientJobId": cid,
        "has_posted_timestamp": has_posted_ts,
        "posted_timestamp_text": posted_ts_str,
        "has_stray_dot": has_stray_dot,
        "has_careers_url": has_careers_url,
        "fraud_warning_variant": fraud_variant,
        "has_trailing_address": has_trailing_addr,
        "trailing_address_text": trailing_text,
        "has_pay_block": has_pay_block,
        "url": url,
    }
    records.append(rec)
    
    if has_posted_ts:
        timestamp_records.append({
            "Job ID": jid,
            "Title": title,
            "Location": loc,
            "Posted Timestamp Extracted": posted_ts_str,
            "Original Description Preview (First 150 chars)": desc[:150],
            "Cleaned Description Preview (First 150 chars)": cleaned_desc[:150],
            "Job URL": url
        })
        
    if has_stray_dot:
        stray_dot_records.append({
            "Job ID": jid,
            "Title": title,
            "Location": loc,
            "Artifact Found": "<p><strong>.</strong></p>",
            "Original Start": desc[:120],
            "Cleaned Start": cleaned_desc[:120],
            "Job URL": url
        })
        
    if has_careers_url:
        careers_url_records.append({
            "Job ID": jid,
            "Title": title,
            "Location": loc,
            "Outbound Link Warning Variant": fraud_variant,
            "Job URL": url
        })
        
    if has_trailing_addr:
        trailing_addr_records.append({
            "Job ID": jid,
            "Title": title,
            "Location": loc,
            "Trailing Address Extracted": trailing_text,
            "Job URL": url
        })

df_all = pd.DataFrame(records)
df_ts = pd.DataFrame(timestamp_records)
df_dot = pd.DataFrame(stray_dot_records)
df_url = pd.DataFrame(careers_url_records)
df_addr = pd.DataFrame(trailing_addr_records)

out_dir = r"c:\Users\JOBIAK\Documents\Python\antigravity"
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"

# Save CSVs
df_all.to_csv(os.path.join(out_dir, "YES_Communities_Description_Issues_Full_Audit.csv"), index=False)
df_all.to_csv(os.path.join(artifact_dir, "YES_Communities_Description_Issues_Full_Audit.csv"), index=False)

df_ts.to_csv(os.path.join(out_dir, "YES_Communities_250_Posted_Timestamp_Jobs.csv"), index=False)
df_ts.to_csv(os.path.join(artifact_dir, "YES_Communities_250_Posted_Timestamp_Jobs.csv"), index=False)

df_addr.to_csv(os.path.join(out_dir, "YES_Communities_198_Trailing_Address_Jobs.csv"), index=False)
df_addr.to_csv(os.path.join(artifact_dir, "YES_Communities_198_Trailing_Address_Jobs.csv"), index=False)

print("CSVs generated successfully.")

# Build Styled Excel Workbook
excel_path = os.path.join(out_dir, "YES_Communities_Description_Audit_Report.xlsx")
wb = openpyxl.Workbook()
# remove default sheet
wb.remove(wb.active)

# Styles
navy_dark = "1B365D"
navy_med = "2E5B88"
navy_light = "D9E1F2"
gray_light = "F2F2F2"
red_soft = "F8CECC"
amber_soft = "FFF2CC"
green_soft = "D5E8D4"

font_title = Font(name="Calibri", size=16, bold=True, color="1B365D")
font_sub = Font(name="Calibri", size=11, italic=True, color="595959")
font_sec = Font(name="Calibri", size=13, bold=True, color="1B365D")
font_hdr = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
font_bold = Font(name="Calibri", size=11, bold=True)
font_regular = Font(name="Calibri", size=11)
font_code = Font(name="Consolas", size=10)

fill_hdr_dark = PatternFill(start_color=navy_dark, end_color=navy_dark, fill_type="solid")
fill_hdr_med = PatternFill(start_color=navy_med, end_color=navy_med, fill_type="solid")
fill_zebra = PatternFill(start_color=gray_light, end_color=gray_light, fill_type="solid")
fill_red = PatternFill(start_color=red_soft, end_color=red_soft, fill_type="solid")
fill_amber = PatternFill(start_color=amber_soft, end_color=amber_soft, fill_type="solid")
fill_green = PatternFill(start_color=green_soft, end_color=green_soft, fill_type="solid")

thin_border_side = Side(style='thin', color='D9D9D9')
border_cell = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
border_total = Border(top=Side(style='thin', color='1B365D'), bottom=Side(style='double', color='1B365D'))

# ----------------- TAB 1: Audit_Summary -----------------
ws1 = wb.create_sheet(title="Audit_Summary")
ws1.views.sheetView[0].showGridLines = True

ws1.append(["YES Communities - Job Descriptions Quality & Audit Report"])
ws1.append(["Comprehensive scan of all 884 posted jobs for ATS artifacts, stale date strings, stray characters, and unwanted URLs"])
ws1.append([])

ws1.cell(1, 1).font = font_title
ws1.cell(2, 1).font = font_sub

ws1.append(["Audit Dimension", "Issue Category", "Affected Jobs", "Total Jobs", "% Impacted", "Cleaning Priority", "Impact on Google for Jobs / CTR"])
for col in range(1, 8):
    c = ws1.cell(4, col)
    c.fill = fill_hdr_dark
    c.font = font_hdr
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

summary_rows = [
    ("Leading Scrape Timestamps", "ATS Scraping Artifact", len(df_ts), len(jobs), len(df_ts)/len(jobs), "CRITICAL (P0)", "Displays stale date in Google Search snippet; leads candidates to believe job is expired."),
    ("Stray Dot Prefix (<p><strong>.</strong></p>)", "HTML Formatting Error", len(df_dot), len(jobs), len(df_dot)/len(jobs), "CRITICAL (P0)", "Renders ugly rogue bullet at top of description & snippet in all GroundsKeeper jobs."),
    ("Outbound Careers Website Links", "Traffic & Apply Leak", len(df_url), len(jobs), len(df_url)/len(jobs), "HIGH (P1)", "Directs candidates to leave proxy apply flow and visit yescommunities.com/careers/ directly."),
    ("Trailing Un-Tagged Addresses", "Malformed HTML Layout", len(df_addr), len(jobs), len(df_addr)/len(jobs), "HIGH (P1)", "Raw text hanging after final </p> tag; causes layout breaks on web browsers and duplicate location."),
    ("Raw Pay Type & Min/Max Rate Tags", "ATS Database Dump", len(jobs), len(jobs), 1.0, "MEDIUM (P2)", "Raw unstyled ATS tags (<p><strong>Pay Type:</strong> Hourly</p>); compensation should be structured schema.")
]

for row_idx, r in enumerate(summary_rows, start=5):
    ws1.append(list(r))
    for col_idx in range(1, 8):
        c = ws1.cell(row_idx, col_idx)
        c.font = font_regular
        c.border = border_cell
        if col_idx in (3, 4):
            c.number_format = "#,##0"
            c.alignment = Alignment(horizontal="right")
        elif col_idx == 5:
            c.number_format = "0.0%"
            c.alignment = Alignment(horizontal="right")
        elif col_idx == 6:
            c.alignment = Alignment(horizontal="center")
            if "CRITICAL" in str(r[5]):
                c.fill = fill_red
                c.font = font_bold
            elif "HIGH" in str(r[5]):
                c.fill = fill_amber
                c.font = font_bold
            else:
                c.fill = fill_green

ws1.append([])
ws1.append(["Top Scraped Timestamp Examples in YES Communities Descriptions:"])
ws1.cell(ws1.max_row, 1).font = font_sec

dt_counts = df_ts["Posted Timestamp Extracted"].value_counts().head(10)
ws1.append(["Extracted Timestamp String", "Jobs Impacted", "User Query Match?"])
ws1.cell(ws1.max_row, 1).fill = fill_hdr_med
ws1.cell(ws1.max_row, 2).fill = fill_hdr_med
ws1.cell(ws1.max_row, 3).fill = fill_hdr_med
for col in (1, 2, 3):
    ws1.cell(ws1.max_row, col).font = font_hdr

for ts_str, cnt in dt_counts.items():
    is_match = "YES (Exact User Example!)" if "September 2, 2026, 4:00 AM" in ts_str else "Same ATS Pattern"
    ws1.append([ts_str, cnt, is_match])
    curr = ws1.max_row
    for col in (1, 2, 3):
        c = ws1.cell(curr, col)
        c.font = font_regular
        c.border = border_cell
        if col == 2:
            c.number_format = "#,##0"
            c.alignment = Alignment(horizontal="right")
        elif col == 3 and "Exact" in is_match:
            c.fill = fill_amber
            c.font = font_bold

# ----------------- TAB 2: Timestamp_Jobs_250 -----------------
ws2 = wb.create_sheet(title="Timestamp_Jobs_250")
ws2.views.sheetView[0].showGridLines = True
ws2.append(["All 250 Jobs Containing Leading 'Posted [Date/Time]' Scrape Artifacts"])
ws2.append(["These jobs display outdated dates in plain text before the first HTML tag."])
ws2.append([])
ws2.cell(1, 1).font = font_sec
ws2.cell(2, 1).font = font_sub

headers2 = list(df_ts.columns)
ws2.append(headers2)
for col in range(1, len(headers2) + 1):
    c = ws2.cell(4, col)
    c.fill = fill_hdr_dark
    c.font = font_hdr
    c.alignment = Alignment(horizontal="center", vertical="center")

for row_idx, r in enumerate(df_ts.to_dict("records"), start=5):
    row_vals = [r[col] for col in headers2]
    ws2.append(row_vals)
    for col_idx in range(1, len(headers2) + 1):
        c = ws2.cell(row_idx, col_idx)
        c.font = font_regular
        c.border = border_cell
        if col_idx in (4, 5, 6):
            c.font = font_code

# ----------------- TAB 3: Stray_Dot_Jobs_36 -----------------
ws3 = wb.create_sheet(title="Stray_Dot_Jobs_36")
ws3.views.sheetView[0].showGridLines = True
ws3.append(["All 36 GroundsKeeper Jobs Starting With Stray Dot '<p><strong>.</strong></p>'"])
ws3.append(["Rogue period character at the very beginning of description."])
ws3.append([])
ws3.cell(1, 1).font = font_sec
ws3.cell(2, 1).font = font_sub

headers3 = list(df_dot.columns)
ws3.append(headers3)
for col in range(1, len(headers3) + 1):
    c = ws3.cell(4, col)
    c.fill = fill_hdr_dark
    c.font = font_hdr

for row_idx, r in enumerate(df_dot.to_dict("records"), start=5):
    row_vals = [r[col] for col in headers3]
    ws3.append(row_vals)
    for col_idx in range(1, len(headers3) + 1):
        c = ws3.cell(row_idx, col_idx)
        c.font = font_regular
        c.border = border_cell
        if col_idx in (4, 5, 6):
            c.font = font_code

# ----------------- TAB 4: Careers_URL_Jobs_847 -----------------
ws4 = wb.create_sheet(title="Careers_URL_Jobs_847")
ws4.views.sheetView[0].showGridLines = True
ws4.append(["Jobs Containing Outbound Direct Apply Links & Fraud Warnings (847 Jobs)"])
ws4.append(["Paragraphs advising candidates to visit yescommunities.com/careers/ directly."])
ws4.append([])
ws4.cell(1, 1).font = font_sec
ws4.cell(2, 1).font = font_sub

headers4 = list(df_url.columns)
ws4.append(headers4)
for col in range(1, len(headers4) + 1):
    c = ws4.cell(4, col)
    c.fill = fill_hdr_dark
    c.font = font_hdr

for row_idx, r in enumerate(df_url.to_dict("records"), start=5):
    row_vals = [r[col] for col in headers4]
    ws4.append(row_vals)
    for col_idx in range(1, len(headers4) + 1):
        c = ws4.cell(row_idx, col_idx)
        c.font = font_regular
        c.border = border_cell

# ----------------- TAB 5: Trailing_Address_Jobs_198 -----------------
ws5 = wb.create_sheet(title="Trailing_Address_Jobs_198")
ws5.views.sheetView[0].showGridLines = True
ws5.append(["Jobs With Trailing Un-Tagged Address Floating After Final Tag (198 Jobs)"])
ws5.append(["Raw physical street address appended outside HTML tags."])
ws5.append([])
ws5.cell(1, 1).font = font_sec
ws5.cell(2, 1).font = font_sub

headers5 = list(df_addr.columns)
ws5.append(headers5)
for col in range(1, len(headers5) + 1):
    c = ws5.cell(4, col)
    c.fill = fill_hdr_dark
    c.font = font_hdr

for row_idx, r in enumerate(df_addr.to_dict("records"), start=5):
    row_vals = [r[col] for col in headers5]
    ws5.append(row_vals)
    for col_idx in range(1, len(headers5) + 1):
        c = ws5.cell(row_idx, col_idx)
        c.font = font_regular
        c.border = border_cell

# ----------------- TAB 6: Cleaning_Rules_Reference -----------------
ws6 = wb.create_sheet(title="Cleaning_Rules_Reference")
ws6.views.sheetView[0].showGridLines = True
ws6.append(["Standardized Cleaning & Removal Rules for YES Communities Job Descriptions"])
ws6.append(["Python Regex and logic to clean production database without data loss"])
ws6.append([])
ws6.cell(1, 1).font = font_sec
ws6.cell(2, 1).font = font_sub

ws6.append(["Issue #", "Issue Name", "Regex / Cleaning Logic", "Before Example", "After Cleaned"])
for col in range(1, 6):
    c = ws6.cell(4, col)
    c.fill = fill_hdr_dark
    c.font = font_hdr

rules = [
    (1, "Leading Posted Timestamp", "re.sub(r'^\\s*Posted\\s+[A-Za-z]+,?\\s+[A-Za-z]+\\s+\\d{1,2},?\\s+\\d{4},?\\s+\\d{1,2}:\\d{2}\\s*(?:AM|PM)?\\s*', '', desc, flags=re.I)", "Posted Wednesday, September 2, 2026, 4:00 AM <p><strong>Community Manager</strong></p>", "<p><strong>Community Manager</strong></p>"),
    (2, "Stray Dot Prefix", "re.sub(r'^\\s*<p><strong>\\s*\\.\\s*</strong></p>\\s*', '', desc, flags=re.I)", "<p><strong>.</strong></p><p><strong>Grounds Keeper</strong></p>", "<p><strong>Grounds Keeper</strong></p>"),
    (3, "Trailing Un-Tagged Address", "last_gt = desc.rfind('>'); desc = desc[:last_gt+1].strip()", "<p><strong>Hiring Max Rate:</strong> 19 USD</p>8401 E Saddlebrook Dr, North Charleston, SC 29406, USA", "<p><strong>Hiring Max Rate:</strong> 19 USD</p>"),
    (4, "Outbound Careers Direct Link", "desc.replace('https://www.yescommunities.com/Careers', '').replace('visit yescommunities.com/careers/ directly for confirmed position openings.', '')", "visit yescommunities.com/careers/ directly for confirmed position openings.", ""),
]

for row_idx, r in enumerate(rules, start=5):
    ws6.append(list(r))
    for col_idx in range(1, 6):
        c = ws6.cell(row_idx, col_idx)
        c.font = font_code if col_idx in (3, 4, 5) else font_regular
        c.border = border_cell

# Auto-fit columns across all sheets
for ws in wb.worksheets:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or '')
            if len(val) > max_len and len(val) < 80:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

wb.save(excel_path)
wb.save(os.path.join(artifact_dir, "YES_Communities_Description_Audit_Report.xlsx"))
print(f"Workbook saved to {excel_path} and artifact dir.")
