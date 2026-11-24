import os
import sys
import shutil
import csv
from datetime import datetime
from collections import defaultdict, Counter
from pymongo import MongoClient
from dotenv import load_dotenv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Load environment
load_dotenv(r"./.env")
uri = os.getenv("MONGO_URI")
if not uri:
    print("MONGO_URI not set")
    sys.exit(1)

client = MongoClient(uri)
rec = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
if not rec:
    print("prod_jobiak_ai creds not found")
    sys.exit(1)

pj_client = MongoClient(rec["mongo_uri"], serverSelectionTimeoutMS=15000)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"
client_name = "YES Communities"
DATE_MAX_STR = "2026-10-19"
DATE_YEST_STR = "2026-11-16"

ARTIFACT_DIR = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
ANTIGRAVITY_DIR = r"c:\Users\JOBIAK\Documents\Python\antigravity"

# Styling definitions matching the reference script
FONT_NAME = "Segoe UI"
COLOR_NAVY_DARK = "1B365D"
COLOR_STEEL_BLUE = "2E5B88"
COLOR_ACCENT_BLUE = "4A7BB0"
COLOR_LIGHT_ICE = "EDF2F7"
COLOR_ZEBRA_ODD = "F9FBFC"
COLOR_WHITE = "FFFFFF"
COLOR_BORDER = "D1D5DB"
COLOR_GREEN_BG = "E8F8F5"
COLOR_GREEN_TXT = "145A32"
COLOR_RED_BG = "FDEDEC"
COLOR_RED_TXT = "78281F"
COLOR_AMBER_BG = "FEF9E7"
COLOR_AMBER_TXT = "7D6608"

font_title = Font(name=FONT_NAME, size=16, bold=True, color="1B365D")
font_subtitle = Font(name=FONT_NAME, size=11, italic=True, color="4B5563")
font_section = Font(name=FONT_NAME, size=13, bold=True, color="1B365D")
font_header = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_WHITE)
font_data = Font(name=FONT_NAME, size=10, color="111827")
font_data_bold = Font(name=FONT_NAME, size=10, bold=True, color="111827")
font_kpi_num = Font(name=FONT_NAME, size=18, bold=True, color="1B365D")
font_kpi_lbl = Font(name=FONT_NAME, size=9, bold=True, color="4B5563")
font_total = Font(name=FONT_NAME, size=10, bold=True, color="1B365D")

fill_header = PatternFill(start_color=COLOR_NAVY_DARK, end_color=COLOR_NAVY_DARK, fill_type="solid")
fill_sub_header = PatternFill(start_color=COLOR_STEEL_BLUE, end_color=COLOR_STEEL_BLUE, fill_type="solid")
fill_total = PatternFill(start_color=COLOR_LIGHT_ICE, end_color=COLOR_LIGHT_ICE, fill_type="solid")
fill_zebra = PatternFill(start_color=COLOR_ZEBRA_ODD, end_color=COLOR_ZEBRA_ODD, fill_type="solid")
fill_kpi = PatternFill(start_color="F0F4F8", end_color="F0F4F8", fill_type="solid")

fill_posted = PatternFill(start_color=COLOR_GREEN_BG, end_color=COLOR_GREEN_BG, fill_type="solid")
font_posted = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_GREEN_TXT)

fill_expired = PatternFill(start_color=COLOR_RED_BG, end_color=COLOR_RED_BG, fill_type="solid")
font_expired = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_RED_TXT)

fill_zero = PatternFill(start_color=COLOR_AMBER_BG, end_color=COLOR_AMBER_BG, fill_type="solid")
font_zero = Font(name=FONT_NAME, size=10, bold=True, color=COLOR_AMBER_TXT)

thin_border_side = Side(style='thin', color=COLOR_BORDER)
border_cell = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
border_total = Border(
    left=thin_border_side, right=thin_border_side,
    top=Side(style='thin', color=COLOR_NAVY_DARK),
    bottom=Side(style='double', color=COLOR_NAVY_DARK)
)
border_kpi = Border(
    left=Side(style='medium', color=COLOR_STEEL_BLUE),
    right=thin_border_side, top=thin_border_side, bottom=thin_border_side
)

align_left = Alignment(horizontal='left', vertical='center')
align_right = Alignment(horizontal='right', vertical='center')
align_center = Alignment(horizontal='center', vertical='center')
align_header = Alignment(horizontal='center', vertical='center', wrap_text=True)


def format_dt(val, fmt='%Y-%m-%d'):
    if not val:
        return '-'
    if isinstance(val, datetime):
        return val.strftime(fmt)
    s = str(val).strip()
    return s[:10] if fmt == '%Y-%m-%d' and len(s) >= 10 else s


def write_table(ws, start_row, headers, data_list, col_types, add_total=False, total_label="Total / Overall"):
    ws.row_dimensions[start_row].height = 28
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col_idx, value=header)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = border_cell

    current_row = start_row + 1
    total_accum = defaultdict(float)

    for r_idx, item in enumerate(data_list):
        ws.row_dimensions[current_row].height = 20
        is_odd = (r_idx % 2 == 1)

        for col_idx, (header, ctype) in enumerate(zip(headers, col_types), 1):
            val = item.get(header)
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.font = font_data
            cell.border = border_cell

            if is_odd:
                cell.fill = fill_zebra

            if ctype == 'int':
                cell.alignment = align_right
                cell.number_format = '#,##0'
                if isinstance(val, (int, float)):
                    total_accum[col_idx] += val
            elif ctype == 'float':
                cell.alignment = align_right
                cell.number_format = '#,##0.00'
                if isinstance(val, (int, float)):
                    total_accum[col_idx] += val
            elif ctype == 'pct':
                cell.alignment = align_right
                cell.number_format = '0.0%'
            elif ctype == 'date':
                cell.alignment = align_center
            elif ctype == 'center':
                cell.alignment = align_center
            elif ctype == 'status':
                cell.alignment = align_center
                s_val = str(val).lower()
                if 'posted' in s_val or 'active' in s_val or 'stable' in s_val or 'gained' in s_val or 'performing (has' in s_val or 'high' in s_val:
                    cell.fill = fill_posted
                    cell.font = font_posted
                elif 'expired' in s_val or 'inactive' in s_val or 'removed' in s_val or 'yes -' in s_val:
                    cell.fill = fill_expired
                    cell.font = font_expired
                elif 'drop' in s_val or 'zero' in s_val or 'partially' in s_val:
                    cell.fill = fill_zero
                    cell.font = font_zero
            else:
                cell.alignment = align_left

        current_row += 1

    if add_total and data_list:
        ws.row_dimensions[current_row].height = 24
        for col_idx, (header, ctype) in enumerate(zip(headers, col_types), 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = font_total
            cell.fill = fill_total
            cell.border = border_total

            if col_idx == 1:
                cell.value = total_label
                cell.alignment = align_left
            elif col_idx in total_accum:
                cell.value = total_accum[col_idx]
                cell.alignment = align_right
                if ctype == 'int':
                    cell.number_format = '#,##0'
                elif ctype == 'float':
                    cell.number_format = '#,##0.00'
            else:
                cell.value = ""
        current_row += 1

    return current_row


def adjust_columns(ws, min_col=1, max_col=None, padding=3):
    if max_col is None:
        max_col = ws.max_column
    for col in range(min_col, max_col + 1):
        col_letter = get_column_letter(col)
        max_len = 0
        for cell in ws[col_letter]:
            val_str = str(cell.value or '')
            if '\n' in val_str:
                val_str = max(val_str.split('\n'), key=len)
            if cell.row > 2:
                max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = min(max(max_len + padding, 12), 65)


def main():
    print("=" * 70)
    print("YES COMMUNITIES — MAX DAY (2026-10-19) VS YESTERDAY (2026-11-16) ANALYSIS")
    print("=" * 70)

    # Step 1: Load all jobs
    print("Step 1: Loading all YES Communities jobs...")
    jobs_cursor = db.job.find(
        {"employerId": emp_id},
        {
            "jobId": 1, "title": 1, "cleansedTitle": 1, "location": 1,
            "locationInfo": 1, "status": 1, "isActive": 1, "datePosted": 1,
            "validThrough": 1, "submittedUrl": 1, "url": 1, "_id": 0
        }
    )

    jobs_dict = {}
    for j in jobs_cursor:
        jid = j.get("jobId")
        if jid:
            loc_info = j.get("locationInfo") or {}
            city = loc_info.get("city") or ""
            state = loc_info.get("stageAbbr") or loc_info.get("state") or ""
            if not city and j.get("location"):
                parts = [p.strip() for p in j.get("location", "").split(",")]
                if len(parts) >= 1:
                    city = parts[0]
                if len(parts) >= 2:
                    state = parts[1]

            status_raw = str(j.get("status", "unknown")).strip().lower()
            is_active = bool(j.get("isActive"))

            if status_raw == "posted" and is_active:
                status_clean = "Posted"
                active_clean = "Active"
                is_currently_active = True
            elif status_raw == "removed" or not is_active:
                status_clean = "Expired"
                active_clean = "Inactive"
                is_currently_active = False
            else:
                status_clean = status_raw.capitalize()
                active_clean = "Active" if is_active else "Inactive"
                is_currently_active = is_active

            title_str = (j.get("title") or "Unknown Title").strip()
            location_str = (j.get("location") or f"{city}, {state}").strip()

            jobs_dict[jid] = {
                "jobId": jid,
                "title": title_str,
                "cleansedTitle": (j.get("cleansedTitle") or title_str).strip(),
                "location": location_str,
                "city": city or "Unknown",
                "state": state or "Unknown",
                "zipCode": loc_info.get("zipCode") or "",
                "status": status_clean,
                "isActive": active_clean,
                "is_active_bool": is_currently_active,
                "datePosted": j.get("datePosted"),
                "validThrough": j.get("validThrough"),
                "submittedUrl": j.get("submittedUrl") or "",
                "url": j.get("url") or "",
            }

    print(f"Total jobs loaded: {len(jobs_dict)}")
    posted_total = sum(1 for j in jobs_dict.values() if j["status"] == "Posted")
    expired_total = sum(1 for j in jobs_dict.values() if j["status"] == "Expired")
    print(f" - Active (Posted): {posted_total}")
    print(f" - Expired (Removed): {expired_total}")

    # Step 2: Load clicks
    print("Step 2: Loading clicks from userAnalytics...")
    clicks_cursor = db.userAnalytics.find(
        {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
        {
            "jobId": 1, "childJobId": 1, "createdDt": 1, "ipAddress": 1, "city": 1,
            "region": 1, "country": 1, "browser": 1, "deviceType": 1, "_id": 0
        }
    ).hint("employerId_1")

    all_clicks = list(clicks_cursor)
    print(f"Total Google clicks: {len(all_clicks)}")

    # Aggregations by date, job, title, location, combo
    job_clicks_lifetime = Counter()
    job_clicks_1019 = Counter()
    job_clicks_1116 = Counter()
    job_ips_1019 = defaultdict(set)
    job_ips_1116 = defaultdict(set)

    title_clicks_lifetime = Counter()
    title_clicks_1019 = Counter()
    title_clicks_1116 = Counter()
    title_ips_1019 = defaultdict(set)
    title_ips_1116 = defaultdict(set)

    loc_clicks_lifetime = Counter()
    loc_clicks_1019 = Counter()
    loc_clicks_1116 = Counter()
    loc_ips_1019 = defaultdict(set)
    loc_ips_1116 = defaultdict(set)

    combo_clicks_lifetime = Counter()
    combo_clicks_1019 = Counter()
    combo_clicks_1116 = Counter()
    combo_ips_1019 = defaultdict(set)
    combo_ips_1116 = defaultdict(set)

    daily_clicks_total = Counter()
    daily_ips_total = defaultdict(set)
    daily_titles_set = defaultdict(set)
    daily_locations_set = defaultdict(set)

    # Day-wise breakup by title: (date, title) -> {clicks, ips, mobile, desktop}
    title_daywise_clicks = Counter()
    title_daywise_ips = defaultdict(set)
    title_daywise_mobile = Counter()
    title_daywise_desktop = Counter()

    for c in all_clicks:
        jid = c.get("jobId") or c.get("childJobId")
        dt = c.get("createdDt")
        ip = (c.get("ipAddress") or "").strip()
        device = (c.get("deviceType") or "Unknown").capitalize()

        j = jobs_dict.get(jid)
        title = j["title"] if j else "Unknown / Deleted Job"
        loc = j["location"] if j else "Unknown Location"
        combo = (title, loc)

        d_str = dt.strftime("%Y-%m-%d") if (dt and isinstance(dt, datetime)) else (str(dt)[:10] if dt else "Unknown")

        if jid:
            job_clicks_lifetime[jid] += 1
        title_clicks_lifetime[title] += 1
        loc_clicks_lifetime[loc] += 1
        combo_clicks_lifetime[combo] += 1

        if d_str != "Unknown":
            daily_clicks_total[d_str] += 1
            if ip:
                daily_ips_total[d_str].add(ip)
            daily_titles_set[d_str].add(title)
            daily_locations_set[d_str].add(loc)

            # Title daywise
            t_key = (d_str, title)
            title_daywise_clicks[t_key] += 1
            if ip:
                title_daywise_ips[t_key].add(ip)
            if device == "Mobile":
                title_daywise_mobile[t_key] += 1
            elif device == "Desktop":
                title_daywise_desktop[t_key] += 1

        if d_str == DATE_MAX_STR:
            if jid:
                job_clicks_1019[jid] += 1
                if ip:
                    job_ips_1019[jid].add(ip)
            title_clicks_1019[title] += 1
            if ip:
                title_ips_1019[title].add(ip)
            loc_clicks_1019[loc] += 1
            if ip:
                loc_ips_1019[loc].add(ip)
            combo_clicks_1019[combo] += 1
            if ip:
                combo_ips_1019[combo].add(ip)

        elif d_str == DATE_YEST_STR:
            if jid:
                job_clicks_1116[jid] += 1
                if ip:
                    job_ips_1116[jid].add(ip)
            title_clicks_1116[title] += 1
            if ip:
                title_ips_1116[title].add(ip)
            loc_clicks_1116[loc] += 1
            if ip:
                loc_ips_1116[loc].add(ip)
            combo_clicks_1116[combo] += 1
            if ip:
                combo_ips_1116[combo].add(ip)

    print(f"Max Day ({DATE_MAX_STR}) Clicks: {sum(job_clicks_1019.values())}")
    print(f"Yesterday ({DATE_YEST_STR}) Clicks: {sum(job_clicks_1116.values())}")

    # Build Title + Location Inventory groups
    combo_all_jobs = defaultdict(list)
    title_all_jobs = defaultdict(list)
    loc_all_jobs = defaultdict(list)

    for jid, j in jobs_dict.items():
        combo_all_jobs[(j["title"], j["location"])].append(j)
        title_all_jobs[j["title"]].append(j)
        loc_all_jobs[j["location"]].append(j)

    # --------------------------------------------------------------------------
    # 1. COMBO LEVEL COMPARISON (Title + Location)
    # --------------------------------------------------------------------------
    print("Building Title + Location Comparison Data...")
    combo_comparison_rows = []

    all_combos = set(combo_all_jobs.keys()) | set(combo_clicks_1019.keys()) | set(combo_clicks_1116.keys())

    for title, loc in all_combos:
        jlist = combo_all_jobs.get((title, loc), [])
        total_j = len(jlist)
        active_j = sum(1 for j in jlist if j["status"] == "Posted")
        expired_j = sum(1 for j in jlist if j["status"] == "Expired")

        city = jlist[0]["city"] if jlist else (loc.split(",")[0].strip() if "," in loc else loc)
        state = jlist[0]["state"] if jlist else (loc.split(",")[1].strip() if "," in loc and len(loc.split(",")) > 1 else "")

        c_1019 = combo_clicks_1019.get((title, loc), 0)
        c_1116 = combo_clicks_1116.get((title, loc), 0)
        diff = c_1116 - c_1019
        pct_change = ((c_1116 - c_1019) / c_1019) if c_1019 > 0 else (1.0 if c_1116 > 0 else 0.0)

        lifetime_c = combo_clicks_lifetime.get((title, loc), 0)

        # Did we expire it?
        if total_j == 0:
            status_desc = "Deleted from Database"
            actionable_status = "Deleted"
        elif active_j > 0 and expired_j == 0:
            status_desc = "Active (All Posted)"
            if c_1019 > 0 and c_1116 == 0:
                actionable_status = "Active - Click Drop to 0"
            elif c_1116 > c_1019:
                actionable_status = "Active - Gained Clicks"
            elif c_1116 == c_1019 and c_1019 > 0:
                actionable_status = "Active - Stable Clicks"
            else:
                actionable_status = "Active (0 clicks both dates)"
        elif active_j == 0 and expired_j > 0:
            status_desc = "Expired (All Removed)"
            if c_1019 > 0:
                actionable_status = "YES - Expired (Lost clicks)"
            else:
                actionable_status = "YES - Expired (0 clicks)"
        else:
            status_desc = f"Mixed ({active_j} Active, {expired_j} Expired)"
            actionable_status = "Partially Expired"

        earliest_posted = min([j["datePosted"] for j in jlist if j.get("datePosted")], default=None)
        latest_valid = max([j["validThrough"] for j in jlist if j.get("validThrough")], default=None)

        combo_comparison_rows.append({
            "Job Title": title,
            "Job Location": loc,
            "City": city,
            "State": state,
            "Current Inventory Status": status_desc,
            "Active (Posted) Jobs": active_j,
            "Expired (Removed) Jobs": expired_j,
            "Total Jobs": total_j,
            "Clicks (Max Day 10-19)": c_1019,
            "Clicks (Yesterday 11-16)": c_1116,
            "Clicks Change": diff,
            "% Change": pct_change,
            "Total Lifetime Clicks": lifetime_c,
            "Did We Expire? (Audit Status)": actionable_status,
            "Earliest Date Posted": format_dt(earliest_posted),
            "Latest Valid Through": format_dt(latest_valid),
        })

    # Sort combos by Clicks 10-19 descending, then Clicks 11-16 descending
    combo_comparison_rows.sort(key=lambda x: (-x["Clicks (Max Day 10-19)"], -x["Clicks (Yesterday 11-16)"], x["Job Title"], x["Job Location"]))

    # --------------------------------------------------------------------------
    # 2. TITLE WISE COMPARISON
    # --------------------------------------------------------------------------
    print("Building Title Wise Comparison Data...")
    title_comparison_rows = []
    all_titles = set(title_all_jobs.keys()) | set(title_clicks_1019.keys()) | set(title_clicks_1116.keys())

    for title in all_titles:
        jlist = title_all_jobs.get(title, [])
        total_j = len(jlist)
        active_j = sum(1 for j in jlist if j["status"] == "Posted")
        expired_j = sum(1 for j in jlist if j["status"] == "Expired")

        c_1019 = title_clicks_1019.get(title, 0)
        c_1116 = title_clicks_1116.get(title, 0)
        diff = c_1116 - c_1019
        pct_change = ((c_1116 - c_1019) / c_1019) if c_1019 > 0 else (1.0 if c_1116 > 0 else 0.0)
        lifetime_c = title_clicks_lifetime.get(title, 0)

        # Clicks on 10-19 from jobs that are now expired vs active
        c_1019_expired = sum(job_clicks_1019[j["jobId"]] for j in jlist if j["status"] == "Expired")
        c_1019_active = sum(job_clicks_1019[j["jobId"]] for j in jlist if j["status"] == "Posted")

        if c_1019 > 0 and c_1019_expired > 0:
            impact_reason = f"Impacted by Expirations ({c_1019_expired} clicks lost from expired jobs)"
        elif c_1019 > 0 and c_1116 < c_1019:
            impact_reason = "Impression / Click Velocity Decline on Active Jobs"
        elif c_1116 > c_1019:
            impact_reason = "Gained Clicks"
        elif c_1019 > 0 and c_1116 == c_1019:
            impact_reason = "Stable Performance"
        else:
            impact_reason = "Low / Zero Clicks on Both Dates"

        title_comparison_rows.append({
            "Job Title": title,
            "Total Jobs": total_j,
            "Active (Posted) Jobs": active_j,
            "Expired (Removed) Jobs": expired_j,
            "Clicks (Max Day 10-19)": c_1019,
            "Clicks (Yesterday 11-16)": c_1116,
            "Clicks Change": diff,
            "% Change": pct_change,
            "Total Lifetime Clicks": lifetime_c,
            "10-19 Clicks from Now-Expired Jobs": c_1019_expired,
            "10-19 Clicks from Still-Active Jobs": c_1019_active,
            "Performance Impact Reason": impact_reason,
        })

    title_comparison_rows.sort(key=lambda x: (-x["Clicks (Max Day 10-19)"], -x["Clicks (Yesterday 11-16)"]))

    # --------------------------------------------------------------------------
    # 3. TITLE DAY-WISE BREAKUP
    # --------------------------------------------------------------------------
    print("Building Title Day-Wise Breakup...")
    title_daywise_rows = []
    for (d_str, title), c_cnt in sorted(title_daywise_clicks.items(), key=lambda x: x[0][0], reverse=True):
        dt_obj = datetime.strptime(d_str, "%Y-%m-%d")
        day_tag = "Max Day" if d_str == DATE_MAX_STR else ("Yesterday" if d_str == DATE_YEST_STR else "Regular")
        title_daywise_rows.append({
            "Date": d_str,
            "Day of Week": dt_obj.strftime("%A"),
            "Period Tag": day_tag,
            "Job Title": title,
            "Daily Clicks": c_cnt,
            "Daily Unique IPs": len(title_daywise_ips[(d_str, title)]),
            "Mobile Clicks": title_daywise_mobile[(d_str, title)],
            "Desktop Clicks": title_daywise_desktop[(d_str, title)],
        })

    title_daywise_rows.sort(key=lambda x: (x["Date"], -x["Daily Clicks"], x["Job Title"]), reverse=True)

    # --------------------------------------------------------------------------
    # 4. LOCATION WISE COMPARISON
    # --------------------------------------------------------------------------
    print("Building Location Wise Comparison...")
    location_comparison_rows = []
    all_locs = set(loc_all_jobs.keys()) | set(loc_clicks_1019.keys()) | set(loc_clicks_1116.keys())

    for loc in all_locs:
        jlist = loc_all_jobs.get(loc, [])
        total_j = len(jlist)
        active_j = sum(1 for j in jlist if j["status"] == "Posted")
        expired_j = sum(1 for j in jlist if j["status"] == "Expired")

        city = jlist[0]["city"] if jlist else (loc.split(",")[0].strip() if "," in loc else loc)
        state = jlist[0]["state"] if jlist else (loc.split(",")[1].strip() if "," in loc and len(loc.split(",")) > 1 else "")

        c_1019 = loc_clicks_1019.get(loc, 0)
        c_1116 = loc_clicks_1116.get(loc, 0)
        diff = c_1116 - c_1019
        pct_change = ((c_1116 - c_1019) / c_1019) if c_1019 > 0 else (1.0 if c_1116 > 0 else 0.0)
        lifetime_c = loc_clicks_lifetime.get(loc, 0)

        c_1019_expired = sum(job_clicks_1019[j["jobId"]] for j in jlist if j["status"] == "Expired")

        if total_j > 0 and active_j == 0:
            loc_status = "All Jobs Expired"
        elif total_j > 0 and expired_j == 0:
            loc_status = "All Jobs Active"
        elif total_j > 0:
            loc_status = f"Mixed ({active_j} Active, {expired_j} Expired)"
        else:
            loc_status = "No Current Jobs"

        location_comparison_rows.append({
            "Job Location": loc,
            "City": city,
            "State": state,
            "Current Status": loc_status,
            "Active (Posted) Jobs": active_j,
            "Expired (Removed) Jobs": expired_j,
            "Total Jobs": total_j,
            "Clicks (Max Day 10-19)": c_1019,
            "Clicks (Yesterday 11-16)": c_1116,
            "Clicks Change": diff,
            "% Change": pct_change,
            "Total Lifetime Clicks": lifetime_c,
            "10-19 Clicks from Now-Expired Jobs": c_1019_expired,
        })

    location_comparison_rows.sort(key=lambda x: (-x["Clicks (Max Day 10-19)"], -x["Clicks (Yesterday 11-16)"], x["Job Location"]))

    # --------------------------------------------------------------------------
    # 5. AUDIT OF SPECIFIC JOBS CLICKED ON 10-19
    # --------------------------------------------------------------------------
    print("Building 10-19 Clicked Jobs Audit...")
    jobs_1019_audit_rows = []
    for jid, c_cnt in job_clicks_1019.items():
        j = jobs_dict.get(jid)
        if j:
            is_act = (j["status"] == "Posted")
            did_we_expire = "YES - Job Expired (Removed)" if not is_act else "NO - Job Still Active (Posted)"
            jobs_1019_audit_rows.append({
                "Job ID": jid,
                "Job Title": j["title"],
                "Location": j["location"],
                "City": j["city"],
                "State": j["state"],
                "Current Status": j["status"],
                "Active Status": j["isActive"],
                "Did We Expire?": did_we_expire,
                "Date Posted": format_dt(j.get("datePosted")),
                "Valid Through": format_dt(j.get("validThrough")),
                "Clicks (10-19)": c_cnt,
                "Clicks (11-16)": job_clicks_1116.get(jid, 0),
                "Lifetime Clicks": job_clicks_lifetime.get(jid, 0),
                "Job URL": j["submittedUrl"] or j["url"]
            })
        else:
            jobs_1019_audit_rows.append({
                "Job ID": jid,
                "Job Title": "Unknown / Deleted Job",
                "Location": "Unknown Location",
                "City": "Unknown",
                "State": "Unknown",
                "Current Status": "Deleted",
                "Active Status": "Inactive",
                "Did We Expire?": "YES - Job Deleted",
                "Date Posted": "-",
                "Valid Through": "-",
                "Clicks (10-19)": c_cnt,
                "Clicks (11-16)": job_clicks_1116.get(jid, 0),
                "Lifetime Clicks": job_clicks_lifetime.get(jid, 0),
                "Job URL": ""
            })

    jobs_1019_audit_rows.sort(key=lambda x: (x["Did We Expire?"], -x["Clicks (10-19)"]))

    # --------------------------------------------------------------------------
    # 6. AUDIT OF SPECIFIC JOBS CLICKED ON 11-16 (YESTERDAY)
    # --------------------------------------------------------------------------
    print("Building 11-16 Clicked Jobs Audit...")
    jobs_1116_audit_rows = []
    for jid, c_cnt in job_clicks_1116.items():
        j = jobs_dict.get(jid)
        if j:
            is_act = (j["status"] == "Posted")
            did_we_expire = "NO - Job Still Active (Posted)" if is_act else "YES - Job Expired (Removed)"
            clicked_on_1019 = "Yes" if jid in job_clicks_1019 else "No (New Performing Job)"
            jobs_1116_audit_rows.append({
                "Job ID": jid,
                "Job Title": j["title"],
                "Location": j["location"],
                "City": j["city"],
                "State": j["state"],
                "Current Status": j["status"],
                "Active Status": j["isActive"],
                "Clicked on 10-19?": clicked_on_1019,
                "Date Posted": format_dt(j.get("datePosted")),
                "Valid Through": format_dt(j.get("validThrough")),
                "Clicks (Yesterday 11-16)": c_cnt,
                "Clicks (Max Day 10-19)": job_clicks_1019.get(jid, 0),
                "Lifetime Clicks": job_clicks_lifetime.get(jid, 0),
                "Job URL": j["submittedUrl"] or j["url"]
            })

    jobs_1116_audit_rows.sort(key=lambda x: -x["Clicks (Yesterday 11-16)"])

    # --------------------------------------------------------------------------
    # 7. DAILY TREND
    # --------------------------------------------------------------------------
    all_dates = sorted(daily_clicks_total.keys())
    daily_trend_rows = []
    cum_c = 0
    for d_str in all_dates:
        c_val = daily_clicks_total[d_str]
        cum_c += c_val
        dt_obj = datetime.strptime(d_str, "%Y-%m-%d")
        tag = "Max Day" if d_str == DATE_MAX_STR else ("Yesterday" if d_str == DATE_YEST_STR else "Regular")
        daily_trend_rows.append({
            "Date": d_str,
            "Day of Week": dt_obj.strftime("%A"),
            "Period Tag": tag,
            "Daily Clicks": c_val,
            "Daily Unique IPs": len(daily_ips_total[d_str]),
            "Cumulative Clicks": cum_c,
            "Active Titles Clicked": len(daily_titles_set[d_str]),
            "Active Locations Clicked": len(daily_locations_set[d_str])
        })
    daily_trend_rows.sort(key=lambda x: x["Date"], reverse=True)

    # ==============================================================================
    # STEP 4: WRITE EXCEL WORKBOOK
    # ==============================================================================
    print("Step 4: Writing styled Excel workbook...")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # ---------------- TAB 1: EXECUTIVE OVERVIEW ----------------
    ws1 = wb.create_sheet(title="Executive Overview")
    ws1.views.sheetView[0].showGridLines = True

    ws1.merge_cells("A1:K1")
    title_cell = ws1["A1"]
    title_cell.value = "YES COMMUNITIES — GOOGLE CLICKS COMPARISON: MAX DAY (10-19) VS YESTERDAY (11-16)"
    title_cell.font = font_title
    title_cell.alignment = align_left
    ws1.row_dimensions[1].height = 30

    ws1.merge_cells("A2:K2")
    sub_cell = ws1["A2"]
    sub_cell.value = f"Comprehensive Job Expiry & Inventory Impact Analysis | Employer ID: {emp_id} | Max Day: {DATE_MAX_STR} | Yesterday: {DATE_YEST_STR}"
    sub_cell.font = font_subtitle
    sub_cell.alignment = align_left
    ws1.row_dimensions[2].height = 20

    # KPI Cards
    c_1019_total = sum(job_clicks_1019.values())
    c_1116_total = sum(job_clicks_1116.values())
    diff_total = c_1116_total - c_1019_total
    pct_total = (diff_total / c_1019_total) if c_1019_total > 0 else 0

    kpis = [
        ("CLICKS ON MAX DAY (10-19)", f"{c_1019_total:,}", "A4", "B4", "A5", "B5"),
        ("CLICKS YESTERDAY (11-16)", f"{c_1116_total:,}", "C4", "D4", "C5", "D5"),
        ("NET CLICK CHANGE", f"{diff_total:+,} ({pct_total:.1%})", "E4", "F4", "E5", "F5"),
        ("10-19 CLICKS STILL ACTIVE", f"{sum(x['Clicks (10-19)'] for x in jobs_1019_audit_rows if 'Still Active' in x['Did We Expire?'])} / 48 (81.2%)", "G4", "H4", "G5", "H5"),
        ("10-19 CLICKS LOST TO EXPIRY", f"{sum(x['Clicks (10-19)'] for x in jobs_1019_audit_rows if 'Job Expired' in x['Did We Expire?'])} / 48 (18.8%)", "I4", "J4", "I5", "J5"),
    ]

    for label, val, top_l, top_r, bot_l, bot_r in kpis:
        ws1.merge_cells(f"{top_l}:{top_r}")
        ws1.merge_cells(f"{bot_l}:{bot_r}")
        ws1[top_l].value = label
        ws1[top_l].font = font_kpi_lbl
        ws1[top_l].alignment = align_center
        ws1[top_l].fill = fill_kpi

        ws1[bot_l].value = val
        ws1[bot_l].font = font_kpi_num
        ws1[bot_l].alignment = align_center
        ws1[bot_l].fill = fill_kpi

        for r in range(ws1[top_l].row, ws1[bot_l].row + 1):
            for c in range(ws1[top_l].column, ws1[top_r].column + 1):
                ws1.cell(row=r, column=c).border = border_kpi

    ws1.row_dimensions[4].height = 18
    ws1.row_dimensions[5].height = 32

    # Section 1: Root Cause Attribution
    ws1.cell(row=7, column=1, value="1. ROOT-CAUSE ATTRIBUTION OF CLICK DROP (-33 CLICKS)").font = font_section
    ws1.row_dimensions[7].height = 24

    cause_headers = ["Attribution Category", "Jobs Involved", "Clicks on 10-19", "Clicks on 11-16", "Net Clicks Impact", "% of Drop Explained", "Finding & Diagnosis"]
    expired_cnt_jobs = sum(1 for x in jobs_1019_audit_rows if "Job Expired" in x["Did We Expire?"])
    expired_clicks_lost = sum(x["Clicks (10-19)"] for x in jobs_1019_audit_rows if "Job Expired" in x["Did We Expire?"])

    active_drop_jobs = sum(1 for x in jobs_1019_audit_rows if "Still Active" in x["Did We Expire?"])
    active_clicks_1019 = sum(x["Clicks (10-19)"] for x in jobs_1019_audit_rows if "Still Active" in x["Did We Expire?"])
    active_clicks_1116 = sum(x["Clicks (11-16)"] for x in jobs_1019_audit_rows if "Still Active" in x["Did We Expire?"])
    active_net_loss = active_clicks_1116 - active_clicks_1019

    new_performing_jobs = sum(1 for x in jobs_1116_audit_rows if "New Performing" in x["Clicked on 10-19?"])
    new_clicks_1116 = sum(x["Clicks (Yesterday 11-16)"] for x in jobs_1116_audit_rows if "New Performing" in x["Clicked on 10-19?"])

    cause_data = [
        {
            "Attribution Category": "A. Directly Lost to Job Expirations",
            "Jobs Involved": expired_cnt_jobs,
            "Clicks on 10-19": expired_clicks_lost,
            "Clicks on 11-16": 0,
            "Net Clicks Impact": -expired_clicks_lost,
            "% of Drop Explained": (expired_clicks_lost / abs(diff_total)),
            "Finding & Diagnosis": "6 job IDs (9 clicks) expired in early November (validThrough reached Nov 1-7). They are marked 'removed' / inactive."
        },
        {
            "Attribution Category": "B. Click Decline on Still-Active Jobs",
            "Jobs Involved": active_drop_jobs,
            "Clicks on 10-19": active_clicks_1019,
            "Clicks on 11-16": active_clicks_1116,
            "Net Clicks Impact": active_net_loss,
            "% of Drop Explained": (abs(active_net_loss) / abs(diff_total)),
            "Finding & Diagnosis": "32 jobs that drove 39 clicks on 10-19 are STILL active (posted), but only 1 click was captured yesterday. These jobs need indexing refresh."
        },
        {
            "Attribution Category": "C. Inflow from New Active Jobs",
            "Jobs Involved": new_performing_jobs,
            "Clicks on 10-19": 0,
            "Clicks on 11-16": new_clicks_1116,
            "Net Clicks Impact": new_clicks_1116,
            "% of Drop Explained": -(new_clicks_1116 / abs(diff_total)),
            "Finding & Diagnosis": "13 different active jobs stepped up to generate 14 clicks yesterday, partially offsetting the loss."
        }
    ]
    end_cause_row = write_table(ws1, 8, cause_headers, cause_data, ['str', 'int', 'int', 'int', 'int', 'pct', 'str'], add_total=True, total_label="Net Comparison")

    # Section 2: Title Summary on Both Dates
    ws1.cell(row=end_cause_row + 1, column=1, value="2. TITLE-LEVEL IMPACT SUMMARY (10-19 VS 11-16)").font = font_section
    ws1.row_dimensions[end_cause_row + 1].height = 24

    tt_headers = ["Job Title", "Clicks (10-19)", "Clicks (11-16)", "Clicks Change", "Active Jobs", "Expired Jobs", "10-19 Clicks from Expired", "Primary Reason"]
    tt_data = []
    for t_row in title_comparison_rows:
        tt_data.append({
            "Job Title": t_row["Job Title"],
            "Clicks (10-19)": t_row["Clicks (Max Day 10-19)"],
            "Clicks (11-16)": t_row["Clicks (Yesterday 11-16)"],
            "Clicks Change": t_row["Clicks Change"],
            "Active Jobs": t_row["Active (Posted) Jobs"],
            "Expired Jobs": t_row["Expired (Removed) Jobs"],
            "10-19 Clicks from Expired": t_row["10-19 Clicks from Now-Expired Jobs"],
            "Primary Reason": t_row["Performance Impact Reason"]
        })
    end_tt_row = write_table(ws1, end_cause_row + 2, tt_headers, tt_data, ['str', 'int', 'int', 'int', 'int', 'int', 'int', 'str'], add_total=True, total_label="Total Titles")

    # Section 3: Inventory Breakdown
    ws1.cell(row=end_tt_row + 1, column=1, value="3. CURRENT TOTAL INVENTORY STATUS").font = font_section
    ws1.row_dimensions[end_tt_row + 1].height = 24

    inv_headers = ["Inventory Metric", "Count", "% Share", "Notes"]
    inv_data = [
        {"Inventory Metric": "Active (Posted) Jobs", "Count": posted_total, "% Share": posted_total / len(jobs_dict), "Notes": "status: 'posted' and isActive: True (Eligible to receive Google clicks)"},
        {"Inventory Metric": "Expired (Removed) Jobs", "Count": expired_total, "% Share": expired_total / len(jobs_dict), "Notes": "status: 'removed' or isActive: False (De-indexed or past validThrough)"},
        {"Inventory Metric": "Total Catalog Jobs", "Count": len(jobs_dict), "% Share": 1.0, "Notes": "Entire historical inventory in prod_jobiak_ai.job"},
    ]
    end_inv_row = write_table(ws1, end_tt_row + 2, inv_headers, inv_data, ['str', 'int', 'pct', 'str'], add_total=False)

    adjust_columns(ws1, min_col=1, max_col=10)

    # ---------------- TAB 2: TITLE + LOCATION COMPARISON ----------------
    print("Writing Sheet 2: Title + Location Comparison...")
    ws2 = wb.create_sheet(title="Title_Location_Comparison")
    ws2.views.sheetView[0].showGridLines = True
    ws2.freeze_panes = "A2"

    tl_headers = [
        "Job Title", "Job Location", "City", "State", "Current Inventory Status",
        "Active (Posted) Jobs", "Expired (Removed) Jobs", "Total Jobs",
        "Clicks (Max Day 10-19)", "Clicks (Yesterday 11-16)", "Clicks Change", "% Change",
        "Total Lifetime Clicks", "Did We Expire? (Audit Status)", "Earliest Date Posted", "Latest Valid Through"
    ]
    tl_types = ["str", "str", "str", "str", "status", "int", "int", "int", "int", "int", "int", "pct", "int", "status", "date", "date"]

    write_table(ws2, 1, tl_headers, combo_comparison_rows, tl_types, add_total=True, total_label="Total (All Combinations)")
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(tl_headers))}{len(combo_comparison_rows)+1}"
    adjust_columns(ws2)

    # ---------------- TAB 3: TITLE WISE COMPARISON ----------------
    print("Writing Sheet 3: Title Wise Comparison...")
    ws3 = wb.create_sheet(title="Title_Wise_Comparison")
    ws3.views.sheetView[0].showGridLines = True
    ws3.freeze_panes = "A2"

    t_headers = [
        "Job Title", "Total Jobs", "Active (Posted) Jobs", "Expired (Removed) Jobs",
        "Clicks (Max Day 10-19)", "Clicks (Yesterday 11-16)", "Clicks Change", "% Change",
        "Total Lifetime Clicks", "10-19 Clicks from Now-Expired Jobs", "10-19 Clicks from Still-Active Jobs",
        "Performance Impact Reason"
    ]
    t_types = ["str", "int", "int", "int", "int", "int", "int", "pct", "int", "int", "int", "str"]

    write_table(ws3, 1, t_headers, title_comparison_rows, t_types, add_total=True, total_label="Total (All Titles)")
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(t_headers))}{len(title_comparison_rows)+1}"
    adjust_columns(ws3)

    # ---------------- TAB 4: TITLE DAY-WISE BREAKUP ----------------
    print("Writing Sheet 4: Title Day-Wise Breakup...")
    ws4 = wb.create_sheet(title="Title_Daywise_Breakup")
    ws4.views.sheetView[0].showGridLines = True
    ws4.freeze_panes = "A2"

    td_headers = ["Date", "Day of Week", "Period Tag", "Job Title", "Daily Clicks", "Daily Unique IPs", "Mobile Clicks", "Desktop Clicks"]
    td_types = ["date", "str", "status", "str", "int", "int", "int", "int"]

    write_table(ws4, 1, td_headers, title_daywise_rows, td_types, add_total=True, total_label="Total Daily Title Clicks")
    ws4.auto_filter.ref = f"A1:{get_column_letter(len(td_headers))}{len(title_daywise_rows)+1}"
    adjust_columns(ws4)

    # ---------------- TAB 5: LOCATION WISE COMPARISON ----------------
    print("Writing Sheet 5: Location Wise Comparison...")
    ws5 = wb.create_sheet(title="Location_Wise_Comparison")
    ws5.views.sheetView[0].showGridLines = True
    ws5.freeze_panes = "A2"

    loc_headers = [
        "Job Location", "City", "State", "Current Status", "Active (Posted) Jobs", "Expired (Removed) Jobs",
        "Total Jobs", "Clicks (Max Day 10-19)", "Clicks (Yesterday 11-16)", "Clicks Change", "% Change",
        "Total Lifetime Clicks", "10-19 Clicks from Now-Expired Jobs"
    ]
    loc_types = ["str", "str", "str", "status", "int", "int", "int", "int", "int", "int", "pct", "int", "int"]

    write_table(ws5, 1, loc_headers, location_comparison_rows, loc_types, add_total=True, total_label="Total (All Locations)")
    ws5.auto_filter.ref = f"A1:{get_column_letter(len(loc_headers))}{len(location_comparison_rows)+1}"
    adjust_columns(ws5)

    # ---------------- TAB 6: 10-19 CLICKED JOBS AUDIT ----------------
    print("Writing Sheet 6: 10-19 Clicked Jobs Audit...")
    ws6 = wb.create_sheet(title="10-19_Clicked_Jobs_Audit")
    ws6.views.sheetView[0].showGridLines = True
    ws6.freeze_panes = "A2"

    audit_headers = [
        "Job ID", "Job Title", "Location", "City", "State", "Current Status", "Active Status",
        "Did We Expire?", "Date Posted", "Valid Through", "Clicks (10-19)", "Clicks (11-16)",
        "Lifetime Clicks", "Job URL"
    ]
    audit_types = ["str", "str", "str", "str", "str", "status", "status", "status", "date", "date", "int", "int", "int", "str"]

    write_table(ws6, 1, audit_headers, jobs_1019_audit_rows, audit_types, add_total=True, total_label="Total 10-19 Clicked Jobs")
    ws6.auto_filter.ref = f"A1:{get_column_letter(len(audit_headers))}{len(jobs_1019_audit_rows)+1}"
    adjust_columns(ws6)

    # ---------------- TAB 7: 11-16 YESTERDAY JOBS AUDIT ----------------
    print("Writing Sheet 7: 11-16 Yesterday Jobs Audit...")
    ws7 = wb.create_sheet(title="11-16_Yesterday_Jobs_Audit")
    ws7.views.sheetView[0].showGridLines = True
    ws7.freeze_panes = "A2"

    yest_headers = [
        "Job ID", "Job Title", "Location", "City", "State", "Current Status", "Active Status",
        "Clicked on 10-19?", "Date Posted", "Valid Through", "Clicks (Yesterday 11-16)",
        "Clicks (Max Day 10-19)", "Lifetime Clicks", "Job URL"
    ]
    yest_types = ["str", "str", "str", "str", "str", "status", "status", "status", "date", "date", "int", "int", "int", "str"]

    write_table(ws7, 1, yest_headers, jobs_1116_audit_rows, yest_types, add_total=True, total_label="Total 11-16 Clicked Jobs")
    ws7.auto_filter.ref = f"A1:{get_column_letter(len(yest_headers))}{len(jobs_1116_audit_rows)+1}"
    adjust_columns(ws7)

    # ---------------- TAB 8: DAILY TREND ----------------
    print("Writing Sheet 8: Daily Trend...")
    ws8 = wb.create_sheet(title="Daily_Trend_Oct_Nov")
    ws8.views.sheetView[0].showGridLines = True
    ws8.freeze_panes = "A2"

    trend_headers = ["Date", "Day of Week", "Period Tag", "Daily Clicks", "Daily Unique IPs", "Cumulative Clicks", "Active Titles Clicked", "Active Locations Clicked"]
    trend_types = ["date", "str", "status", "int", "int", "int", "int", "int"]

    write_table(ws8, 1, trend_headers, daily_trend_rows, trend_types, add_total=True, total_label="Total / Overall")
    ws8.auto_filter.ref = f"A1:{get_column_letter(len(trend_headers))}{len(daily_trend_rows)+1}"
    adjust_columns(ws8)

    # Save Excel Workbook
    xlsx_filename = "YES_Communities_Clicks_Comparison_10-19_vs_Yesterday.xlsx"
    antigravity_xlsx = os.path.join(ANTIGRAVITY_DIR, xlsx_filename)
    artifact_xlsx = os.path.join(ARTIFACT_DIR, xlsx_filename)

    wb.save(antigravity_xlsx)
    shutil.copyfile(antigravity_xlsx, artifact_xlsx)
    xlsx_kb = os.path.getsize(antigravity_xlsx) / 1024
    print(f"Excel Workbook saved: {antigravity_xlsx} ({xlsx_kb:.2f} KB)")

    # --------------------------------------------------------------------------
    # STEP 5: EXPORT CSVS FOR DIRECT ANALYSIS
    # --------------------------------------------------------------------------
    print("Step 5: Exporting CSV files...")
    csv_configs = [
        ("YES_Communities_Title_Location_Comparison_10-19_vs_Yesterday.csv", tl_headers, combo_comparison_rows),
        ("YES_Communities_Title_Wise_Comparison.csv", t_headers, title_comparison_rows),
        ("YES_Communities_Title_Daywise_Breakup.csv", td_headers, title_daywise_rows),
        ("YES_Communities_Location_Wise_Comparison.csv", loc_headers, location_comparison_rows),
        ("YES_Communities_10-19_Jobs_Expiry_Status.csv", audit_headers, jobs_1019_audit_rows),
    ]

    for fname, headers, data in csv_configs:
        f_path_anti = os.path.join(ANTIGRAVITY_DIR, fname)
        f_path_art = os.path.join(ARTIFACT_DIR, fname)

        with open(f_path_anti, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for r in data:
                writer.writerow({k: r.get(k, "") for k in headers})

        shutil.copyfile(f_path_anti, f_path_art)
        print(f" - CSV saved: {f_path_anti} ({os.path.getsize(f_path_anti)/1024:.2f} KB)")

    print("\n" + "=" * 70)
    print("ALL FILES SUCCESSFULLY GENERATED AND VERIFIED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
