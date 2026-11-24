import os
import sys
import shutil
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

ARTIFACT_DIR = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
ANTIGRAVITY_DIR = r"c:\Users\JOBIAK\Documents\Python\antigravity"

# Styling definitions
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
    # Header row
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

            # Row shading
            if is_odd:
                cell.fill = fill_zebra

            # Alignment & formatting
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
                if 'posted' in s_val or 'active' in s_val or 'performing (has' in s_val or 'high' in s_val:
                    cell.fill = fill_posted
                    cell.font = font_posted
                elif 'expired' in s_val or 'inactive' in s_val:
                    cell.fill = fill_expired
                    cell.font = font_expired
                elif 'non-performing' in s_val or 'zero' in s_val:
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
            if cell.row > 2:  # Skip large title rows
                max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = min(max(max_len + padding, 12), 65)


def generate_report_for_client(emp_id: str, client_name: str, file_slug: str):
    print(f"\n=======================================================")
    print(f"Generating Report for: {client_name} ({emp_id})")
    print(f"=======================================================")

    print(f"Step 1: Loading all {client_name} jobs from prod_jobiak_ai.job...")
    all_jobs_cursor = db.job.find(
        {'employerId': emp_id},
        {
            'jobId': 1, 'title': 1, 'cleansedTitle': 1, 'location': 1,
            'locationInfo': 1, 'status': 1, 'isActive': 1, 'datePosted': 1,
            'validThrough': 1, 'submittedUrl': 1, 'url': 1, '_id': 0
        }
    )

    jobs_dict = {}
    for j in all_jobs_cursor:
        jid = j.get('jobId')
        if jid:
            loc_info = j.get('locationInfo') or {}
            city = loc_info.get('city') or ''
            state = loc_info.get('stageAbbr') or loc_info.get('state') or ''
            if not city and j.get('location'):
                parts = [p.strip() for p in j.get('location', '').split(',')]
                if len(parts) >= 1:
                    city = parts[0]
                if len(parts) >= 2:
                    state = parts[1]

            status_raw = str(j.get('status', 'unknown')).strip().lower()
            is_active = bool(j.get('isActive'))

            if status_raw == 'posted' and is_active:
                status_clean = 'Posted'
                active_clean = 'Active'
            elif status_raw == 'removed' or not is_active:
                status_clean = 'Expired'
                active_clean = 'Inactive'
            else:
                status_clean = status_raw.capitalize()
                active_clean = 'Active' if is_active else 'Inactive'

            title_str = (j.get('title') or 'Unknown Title').strip()
            location_str = (j.get('location') or f"{city}, {state}").strip()

            jobs_dict[jid] = {
                'jobId': jid,
                'title': title_str,
                'cleansedTitle': (j.get('cleansedTitle') or title_str).strip(),
                'location': location_str,
                'city': city or 'Unknown',
                'state': state or 'Unknown',
                'zipCode': loc_info.get('zipCode') or '',
                'status': status_clean,
                'isActive': active_clean,
                'datePosted': j.get('datePosted'),
                'validThrough': j.get('validThrough'),
                'submittedUrl': j.get('submittedUrl') or '',
                'url': j.get('url') or '',
            }

    print(f"Total jobs loaded from database: {len(jobs_dict)}")

    print(f"Step 2: Loading click records from userAnalytics for {client_name}...")
    cursor = db.userAnalytics.find(
        {'employerId': emp_id, 'isFromGoogle': True, 'isBot': False},
        {
            'jobId': 1, 'childJobId': 1, 'createdDt': 1, 'ipAddress': 1, 'city': 1,
            'region': 1, 'country': 1, 'browser': 1, 'browserType': 1,
            'deviceType': 1, 'platform': 1, '_id': 0
        }
    ).hint('employerId_1')

    click_records = list(cursor)
    print(f"Total Google clicks fetched: {len(click_records)}")

    # Structures for aggregation
    job_clicks = Counter()
    job_ips = defaultdict(set)
    job_mobile = Counter()
    job_desktop = Counter()
    job_tablet = Counter()
    job_first_dt = {}
    job_last_dt = {}

    combo_day_clicks = Counter()
    combo_day_ips = defaultdict(set)
    combo_day_mobile = Counter()
    combo_day_desktop = Counter()

    day_total_clicks = Counter()
    day_total_ips = defaultdict(set)
    day_titles_set = defaultdict(set)
    day_locations_set = defaultdict(set)

    visitor_loc_clicks = Counter()
    visitor_loc_ips = defaultdict(set)

    device_counter = Counter()
    browser_counter = Counter()

    for c in click_records:
        jid = c.get('jobId') or c.get('childJobId')
        dt = c.get('createdDt')
        ip = (c.get('ipAddress') or '').strip()
        device = (c.get('deviceType') or 'Unknown').capitalize()
        browser = (c.get('browser') or 'Unknown').strip()
        v_city = (c.get('city') or 'Unknown').strip()
        v_state = (c.get('region') or 'Unknown').strip()
        v_country = (c.get('country') or 'Unknown').strip()

        device_counter[device] += 1
        browser_counter[browser] += 1

        v_key = (v_city, v_state, v_country)
        visitor_loc_clicks[v_key] += 1
        if ip:
            visitor_loc_ips[v_key].add(ip)

        date_str = dt.strftime('%Y-%m-%d') if (dt and isinstance(dt, datetime)) else (str(dt)[:10] if dt else 'Unknown')

        if date_str != 'Unknown':
            day_total_clicks[date_str] += 1
            if ip:
                day_total_ips[date_str].add(ip)

        # Job info
        job_info = jobs_dict.get(jid)
        if job_info:
            title = job_info['title']
            location = job_info['location']
            status = job_info['status']
            is_active = job_info['isActive']
        else:
            title = 'Unknown / Deleted Job'
            location = 'Unknown Location'
            status = 'Unknown'
            is_active = 'Unknown'

        if jid:
            job_clicks[jid] += 1
            if ip:
                job_ips[jid].add(ip)
            if device == 'Mobile':
                job_mobile[jid] += 1
            elif device == 'Desktop':
                job_desktop[jid] += 1
            elif device == 'Tablet':
                job_tablet[jid] += 1

            if dt and isinstance(dt, datetime):
                if jid not in job_first_dt or dt < job_first_dt[jid]:
                    job_first_dt[jid] = dt
                if jid not in job_last_dt or dt > job_last_dt[jid]:
                    job_last_dt[jid] = dt

        if date_str != 'Unknown':
            day_titles_set[date_str].add(title)
            day_locations_set[date_str].add(location)

            combo_key = (date_str, title, location, status, is_active)
            combo_day_clicks[combo_key] += 1
            if ip:
                combo_day_ips[combo_key].add(ip)
            if device == 'Mobile':
                combo_day_mobile[combo_key] += 1
            elif device == 'Desktop':
                combo_day_desktop[combo_key] += 1

    print("Step 3: Aggregating Title, Location, and Combo summaries...")

    title_all_jobs = defaultdict(list)
    location_all_jobs = defaultdict(list)
    combo_all_jobs = defaultdict(list)

    for jid, j in jobs_dict.items():
        title_all_jobs[j['title']].append(j)
        location_all_jobs[j['location']].append(j)
        combo_all_jobs[(j['title'], j['location'])].append(j)

    # Title summary
    title_summary = []
    for title, jlist in title_all_jobs.items():
        total_jobs = len(jlist)
        posted_jobs = sum(1 for j in jlist if j['status'] == 'Posted')
        expired_jobs = sum(1 for j in jlist if j['status'] == 'Expired')

        t_clicks = sum(job_clicks[j['jobId']] for j in jlist)
        t_ips = len(set.union(*[job_ips[j['jobId']] for j in jlist]) if any(job_ips[j['jobId']] for j in jlist) else set())
        perf_jobs = sum(1 for j in jlist if job_clicks[j['jobId']] > 0)
        zero_click_jobs = total_jobs - perf_jobs

        first_dts = [job_first_dt[j['jobId']] for j in jlist if j['jobId'] in job_first_dt]
        last_dts = [job_last_dt[j['jobId']] for j in jlist if j['jobId'] in job_last_dt]
        first_dt_str = min(first_dts).strftime('%Y-%m-%d') if first_dts else '-'
        last_dt_str = max(last_dts).strftime('%Y-%m-%d') if last_dts else '-'

        avg_clicks = round(t_clicks / total_jobs, 2) if total_jobs > 0 else 0
        pct_perf = round(perf_jobs / total_jobs * 100, 1) if total_jobs > 0 else 0

        if t_clicks >= 50:
            perf_tier = "High Performing (50+ clicks)"
        elif t_clicks >= 10:
            perf_tier = "Moderate Performing (10-49 clicks)"
        elif t_clicks > 0:
            perf_tier = "Low Performing (1-9 clicks)"
        else:
            perf_tier = "Non-Performing (0 clicks)"

        title_summary.append({
            'Job Title': title,
            'Total Clicks': t_clicks,
            'Unique Visitors (IPs)': t_ips,
            'Total Jobs Posted': total_jobs,
            'Active (Posted) Jobs': posted_jobs,
            'Expired (Removed) Jobs': expired_jobs,
            'Jobs with Clicks': perf_jobs,
            'Zero-Click Jobs': zero_click_jobs,
            '% Jobs with Clicks': pct_perf / 100.0,
            'Avg Clicks / Job': avg_clicks,
            'First Click Date': first_dt_str,
            'Last Click Date': last_dt_str,
            'Performance Tier': perf_tier,
        })

    title_summary.sort(key=lambda x: (-x['Total Clicks'], -x['Total Jobs Posted']))

    # Location summary
    location_summary = []
    for loc, jlist in location_all_jobs.items():
        total_jobs = len(jlist)
        posted_jobs = sum(1 for j in jlist if j['status'] == 'Posted')
        expired_jobs = sum(1 for j in jlist if j['status'] == 'Expired')

        city = jlist[0]['city']
        state = jlist[0]['state']

        l_clicks = sum(job_clicks[j['jobId']] for j in jlist)
        l_ips = len(set.union(*[job_ips[j['jobId']] for j in jlist]) if any(job_ips[j['jobId']] for j in jlist) else set())
        perf_jobs = sum(1 for j in jlist if job_clicks[j['jobId']] > 0)
        zero_click_jobs = total_jobs - perf_jobs

        first_dts = [job_first_dt[j['jobId']] for j in jlist if j['jobId'] in job_first_dt]
        last_dts = [job_last_dt[j['jobId']] for j in jlist if j['jobId'] in job_last_dt]
        first_dt_str = min(first_dts).strftime('%Y-%m-%d') if first_dts else '-'
        last_dt_str = max(last_dts).strftime('%Y-%m-%d') if last_dts else '-'

        avg_clicks = round(l_clicks / total_jobs, 2) if total_jobs > 0 else 0
        pct_perf = round(perf_jobs / total_jobs * 100, 1) if total_jobs > 0 else 0

        if l_clicks >= 50:
            perf_tier = "High Performing (50+ clicks)"
        elif l_clicks >= 10:
            perf_tier = "Moderate Performing (10-49 clicks)"
        elif l_clicks > 0:
            perf_tier = "Low Performing (1-9 clicks)"
        else:
            perf_tier = "Non-Performing (0 clicks)"

        location_summary.append({
            'Job Location': loc,
            'City': city,
            'State': state,
            'Total Clicks': l_clicks,
            'Unique Visitors (IPs)': l_ips,
            'Total Jobs Posted': total_jobs,
            'Active (Posted) Jobs': posted_jobs,
            'Expired (Removed) Jobs': expired_jobs,
            'Jobs with Clicks': perf_jobs,
            'Zero-Click Jobs': zero_click_jobs,
            '% Jobs with Clicks': pct_perf / 100.0,
            'Avg Clicks / Job': avg_clicks,
            'First Click Date': first_dt_str,
            'Last Click Date': last_dt_str,
            'Performance Tier': perf_tier,
        })

    location_summary.sort(key=lambda x: (-x['Total Clicks'], -x['Total Jobs Posted']))

    # Title + Location Combo Summary
    combo_summary = []
    for (title, loc), jlist in combo_all_jobs.items():
        total_jobs = len(jlist)
        posted_jobs = sum(1 for j in jlist if j['status'] == 'Posted')
        expired_jobs = sum(1 for j in jlist if j['status'] == 'Expired')
        city = jlist[0]['city']
        state = jlist[0]['state']

        c_clicks = sum(job_clicks[j['jobId']] for j in jlist)
        c_ips = len(set.union(*[job_ips[j['jobId']] for j in jlist]) if any(job_ips[j['jobId']] for j in jlist) else set())
        perf_jobs = sum(1 for j in jlist if job_clicks[j['jobId']] > 0)
        zero_click_jobs = total_jobs - perf_jobs

        first_dts = [job_first_dt[j['jobId']] for j in jlist if j['jobId'] in job_first_dt]
        last_dts = [job_last_dt[j['jobId']] for j in jlist if j['jobId'] in job_last_dt]
        first_dt_str = min(first_dts).strftime('%Y-%m-%d') if first_dts else '-'
        last_dt_str = max(last_dts).strftime('%Y-%m-%d') if last_dts else '-'

        status_str = "Posted (Active)" if posted_jobs > 0 else "Expired (Removed)"
        perf_status = "Performing (Has Clicks)" if c_clicks > 0 else "Non-Performing (0 Clicks)"

        combo_summary.append({
            'Job Title': title,
            'Job Location': loc,
            'City': city,
            'State': state,
            'Current Inventory Status': status_str,
            'Total Jobs': total_jobs,
            'Active (Posted) Jobs': posted_jobs,
            'Expired (Removed) Jobs': expired_jobs,
            'Total Clicks': c_clicks,
            'Unique Visitors (IPs)': c_ips,
            'Jobs with Clicks': perf_jobs,
            'Zero-Click Jobs': zero_click_jobs,
            'First Click Date': first_dt_str,
            'Last Click Date': last_dt_str,
            'Performance Status': perf_status,
        })

    combo_summary.sort(key=lambda x: (-x['Total Clicks'], x['Job Title'], x['Job Location']))

    # Title + Location Day-Wise rows
    combo_day_rows = []
    for (d_str, title, loc, status, is_act), c_count in combo_day_clicks.items():
        combo_day_rows.append({
            'Date': d_str,
            'Job Title': title,
            'Job Location': loc,
            'Job Status': status,
            'Active Status': is_act,
            'Daily Clicks': c_count,
            'Daily Unique IPs': len(combo_day_ips[(d_str, title, loc, status, is_act)]),
            'Mobile Clicks': combo_day_mobile[(d_str, title, loc, status, is_act)],
            'Desktop Clicks': combo_day_desktop[(d_str, title, loc, status, is_act)],
        })

    combo_day_rows.sort(key=lambda x: (x['Date'], -x['Daily Clicks'], x['Job Title']), reverse=True)

    # Jobs With Clicks detail
    jobs_with_clicks_rows = []
    for jid, c_count in job_clicks.items():
        j = jobs_dict.get(jid)
        if j:
            first_str = format_dt(job_first_dt.get(jid), '%Y-%m-%d %H:%M:%S')
            last_str = format_dt(job_last_dt.get(jid), '%Y-%m-%d %H:%M:%S')
            posted_str = format_dt(j.get('datePosted'), '%Y-%m-%d')
            valid_str = format_dt(j.get('validThrough'), '%Y-%m-%d')

            jobs_with_clicks_rows.append({
                'Job ID': jid,
                'Job Title': j['title'],
                'Location': j['location'],
                'City': j['city'],
                'State': j['state'],
                'Current Status': j['status'],
                'Active Status': j['isActive'],
                'Date Posted': posted_str,
                'Valid Through': valid_str,
                'Total Clicks': c_count,
                'Unique Visitors (IPs)': len(job_ips[jid]),
                'Mobile Clicks': job_mobile[jid],
                'Desktop Clicks': job_desktop[jid],
                'Tablet Clicks': job_tablet[jid],
                'First Click Timestamp': first_str,
                'Last Click Timestamp': last_str,
                'Job URL': j['submittedUrl'] or j['url'],
            })

    jobs_with_clicks_rows.sort(key=lambda x: (-x['Total Clicks'], x['Job Title']))

    # Zero Click Jobs
    zero_click_jobs_rows = []
    for jid, j in jobs_dict.items():
        if job_clicks[jid] == 0:
            posted_str = format_dt(j.get('datePosted'), '%Y-%m-%d')
            valid_str = format_dt(j.get('validThrough'), '%Y-%m-%d')

            zero_click_jobs_rows.append({
                'Job ID': jid,
                'Job Title': j['title'],
                'Location': j['location'],
                'City': j['city'],
                'State': j['state'],
                'Current Status': j['status'],
                'Active Status': j['isActive'],
                'Date Posted': posted_str,
                'Valid Through': valid_str,
                'Total Clicks': 0,
                'Job URL': j['submittedUrl'] or j['url'],
            })

    zero_click_jobs_rows.sort(key=lambda x: (x['Current Status'], x['Job Title'], x['Location']))

    # Daily Trend
    all_dates = sorted(day_total_clicks.keys())
    daily_trend_rows = []
    cum_clicks = 0
    for d_str in all_dates:
        c_count = day_total_clicks[d_str]
        cum_clicks += c_count
        try:
            dt_obj = datetime.strptime(d_str, '%Y-%m-%d')
            weekday_str = dt_obj.strftime('%A')
        except Exception:
            weekday_str = 'Unknown'

        daily_trend_rows.append({
            'Date': d_str,
            'Day of Week': weekday_str,
            'Daily Clicks': c_count,
            'Daily Unique IPs': len(day_total_ips[d_str]),
            'Cumulative Clicks': cum_clicks,
            'Active Titles Clicked': len(day_titles_set[d_str]),
            'Active Locations Clicked': len(day_locations_set[d_str]),
        })

    daily_trend_rows.sort(key=lambda x: x['Date'], reverse=True)

    # Visitor Locations
    visitor_loc_rows = []
    for (v_city, v_state, v_country), c_count in visitor_loc_clicks.items():
        visitor_loc_rows.append({
            'Visitor City': v_city,
            'Visitor State / Region': v_state,
            'Visitor Country': v_country,
            'Total Clicks': c_count,
            'Unique IPs': len(visitor_loc_ips[(v_city, v_state, v_country)]),
        })
    visitor_loc_rows.sort(key=lambda x: -x['Total Clicks'])

    print(f"Aggregations complete for {client_name}:")
    print(f" - Title summary: {len(title_summary)} titles")
    print(f" - Location summary: {len(location_summary)} locations")
    print(f" - Combo summary: {len(combo_summary)} combinations")
    print(f" - Combo day-wise: {len(combo_day_rows)} daily combo records")
    print(f" - Jobs with clicks: {len(jobs_with_clicks_rows)} jobs")
    print(f" - Zero-click jobs: {len(zero_click_jobs_rows)} jobs")
    print(f" - Daily trend: {len(daily_trend_rows)} days")
    print(f" - Visitor locations: {len(visitor_loc_rows)} visitor locations")

    # Step 4: Write to Openpyxl Excel Workbook
    print(f"Step 4: Creating Excel workbook for {client_name} with professional styling...")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove default sheet

    # ==============================================================================
    # SHEET 1: EXECUTIVE SUMMARY & DASHBOARD
    # ==============================================================================
    print("Writing Sheet 1: Executive Summary...")
    ws1 = wb.create_sheet(title="Executive Summary")
    ws1.views.sheetView[0].showGridLines = True

    # Title block
    ws1.merge_cells("A1:K1")
    title_cell = ws1["A1"]
    title_cell.value = f"{client_name.upper()} — GOOGLE FOR JOBS CLICKS PERFORMANCE REPORT"
    title_cell.font = font_title
    title_cell.alignment = align_left
    ws1.row_dimensions[1].height = 30

    min_d = min(all_dates) if all_dates else "N/A"
    max_d = max(all_dates) if all_dates else "N/A"
    ws1.merge_cells("A2:K2")
    sub_cell = ws1["A2"]
    sub_cell.value = f"Data Analysis Window: Day 1 ({min_d}) to Today ({max_d}) | Total Clicks: {len(click_records):,} | Employer ID: {emp_id}"
    sub_cell.font = font_subtitle
    sub_cell.alignment = align_left
    ws1.row_dimensions[2].height = 20

    # KPI Cards
    total_ips_count = len(set(c['ipAddress'] for c in click_records if c.get('ipAddress')))
    total_jobs_len = len(jobs_dict)
    perf_pct_str = f"({len(job_clicks)/total_jobs_len*100:.1f}%)" if total_jobs_len > 0 else "0%"
    zero_pct_str = f"({len(zero_click_jobs_rows)/total_jobs_len*100:.1f}%)" if total_jobs_len > 0 else "0%"

    kpis = [
        ("TOTAL GOOGLE CLICKS", f"{len(click_records):,}", "A4", "B4", "A5", "B5"),
        ("UNIQUE VISITORS (IPS)", f"{total_ips_count:,}", "C4", "D4", "C5", "D5"),
        ("TOTAL JOBS POSTED", f"{total_jobs_len:,}", "E4", "F4", "E5", "F5"),
        ("PERFORMING JOBS (HAS CLICKS)", f"{len(job_clicks):,} {perf_pct_str}", "G4", "H4", "G5", "H5"),
        ("ZERO-CLICK JOBS", f"{len(zero_click_jobs_rows):,} {zero_pct_str}", "I4", "J4", "I5", "J5"),
    ]

    for label, val, top_l, top_r, bot_l, bot_r in kpis:
        ws1.merge_cells(f"{top_l}:{top_r}")
        ws1.merge_cells(f"{bot_l}:{bot_r}")

        c_top = ws1[top_l]
        c_top.value = label
        c_top.font = font_kpi_lbl
        c_top.alignment = align_center
        c_top.fill = fill_kpi

        c_bot = ws1[bot_l]
        c_bot.value = val
        c_bot.font = font_kpi_num
        c_bot.alignment = align_center
        c_bot.fill = fill_kpi

        for r in range(ws1[top_l].row, ws1[bot_l].row + 1):
            for c in range(ws1[top_l].column, ws1[top_r].column + 1):
                ws1.cell(row=r, column=c).border = border_kpi

    ws1.row_dimensions[4].height = 18
    ws1.row_dimensions[5].height = 32

    # Section: Inventory & Status Breakdown
    ws1.cell(row=7, column=1, value="1. INVENTORY STATUS BREAKDOWN (POSTED VS EXPIRED)").font = font_section
    ws1.row_dimensions[7].height = 24

    inv_headers = ["Metric / Status", "Total Jobs", "Jobs with Clicks", "Zero-Click Jobs", "Total Clicks Received", "Click Share %"]
    posted_jobs_cnt = sum(1 for j in jobs_dict.values() if j['status'] == 'Posted')
    expired_jobs_cnt = sum(1 for j in jobs_dict.values() if j['status'] == 'Expired')

    posted_clicks_cnt = sum(job_clicks[jid] for jid, j in jobs_dict.items() if j['status'] == 'Posted')
    expired_clicks_cnt = sum(job_clicks[jid] for jid, j in jobs_dict.items() if j['status'] == 'Expired')

    posted_perf_cnt = sum(1 for jid, j in jobs_dict.items() if j['status'] == 'Posted' and job_clicks[jid] > 0)
    expired_perf_cnt = sum(1 for jid, j in jobs_dict.items() if j['status'] == 'Expired' and job_clicks[jid] > 0)

    inv_data = [
        {
            "Metric / Status": "Posted (Currently Active Jobs)",
            "Total Jobs": posted_jobs_cnt,
            "Jobs with Clicks": posted_perf_cnt,
            "Zero-Click Jobs": posted_jobs_cnt - posted_perf_cnt,
            "Total Clicks Received": posted_clicks_cnt,
            "Click Share %": (posted_clicks_cnt / len(click_records)) if click_records else 0,
        },
        {
            "Metric / Status": "Expired (Removed Jobs)",
            "Total Jobs": expired_jobs_cnt,
            "Jobs with Clicks": expired_perf_cnt,
            "Zero-Click Jobs": expired_jobs_cnt - expired_perf_cnt,
            "Total Clicks Received": expired_clicks_cnt,
            "Click Share %": (expired_clicks_cnt / len(click_records)) if click_records else 0,
        }
    ]
    end_inv_row = write_table(ws1, 8, inv_headers, inv_data, ['str', 'int', 'int', 'int', 'int', 'pct'], add_total=True, total_label=f"Total {client_name} Inventory")

    # Section: Device & Platform Breakdown
    ws1.cell(row=end_inv_row + 1, column=1, value="2. DEVICE & PLATFORM BREAKDOWN").font = font_section
    ws1.row_dimensions[end_inv_row + 1].height = 24

    dev_headers = ["Device Type", "Total Clicks", "Share %"]
    dev_data = []
    for dev, count in device_counter.most_common():
        dev_data.append({
            "Device Type": dev,
            "Total Clicks": count,
            "Share %": count / len(click_records) if click_records else 0
        })
    end_dev_row = write_table(ws1, end_inv_row + 2, dev_headers, dev_data, ['str', 'int', 'pct'], add_total=True, total_label="Total Device Clicks")

    # Section: Top 10 Performing Job Titles
    ws1.cell(row=end_dev_row + 1, column=1, value="3. TOP 10 PERFORMING JOB TITLES").font = font_section
    ws1.row_dimensions[end_dev_row + 1].height = 24

    top_title_headers = ["Job Title", "Total Clicks", "Unique IPs", "Total Jobs", "Active Jobs", "Expired Jobs", "% Jobs with Clicks", "Avg Clicks/Job"]
    top_title_data = title_summary[:10]
    end_tt_row = write_table(ws1, end_dev_row + 2, top_title_headers, top_title_data, ['str', 'int', 'int', 'int', 'int', 'int', 'pct', 'float'])

    # Section: Top 10 Performing Locations
    ws1.cell(row=end_tt_row + 1, column=1, value="4. TOP 10 PERFORMING JOB LOCATIONS").font = font_section
    ws1.row_dimensions[end_tt_row + 1].height = 24

    top_loc_headers = ["Job Location", "City", "State", "Total Clicks", "Unique IPs", "Total Jobs", "Active Jobs", "Expired Jobs", "% Jobs with Clicks"]
    top_loc_data = location_summary[:10]
    end_tl_row = write_table(ws1, end_tt_row + 2, top_loc_headers, top_loc_data, ['str', 'str', 'str', 'int', 'int', 'int', 'int', 'int', 'pct'])

    adjust_columns(ws1, min_col=1, max_col=10)

    # ==============================================================================
    # SHEET 2: TITLE PERFORMANCE (TITLE-WISE REPORT)
    # ==============================================================================
    print("Writing Sheet 2: Title Performance...")
    ws2 = wb.create_sheet(title="Title Performance")
    ws2.views.sheetView[0].showGridLines = True
    ws2.freeze_panes = "A2"

    title_headers = [
        'Job Title', 'Total Clicks', 'Unique Visitors (IPs)', 'Total Jobs Posted',
        'Active (Posted) Jobs', 'Expired (Removed) Jobs', 'Jobs with Clicks',
        'Zero-Click Jobs', '% Jobs with Clicks', 'Avg Clicks / Job',
        'First Click Date', 'Last Click Date', 'Performance Tier'
    ]
    title_col_types = ['str', 'int', 'int', 'int', 'int', 'int', 'int', 'int', 'pct', 'float', 'date', 'date', 'status']

    write_table(ws2, 1, title_headers, title_summary, title_col_types, add_total=True, total_label="Total (All Titles)")
    ws2.auto_filter.ref = f"A1:{get_column_letter(len(title_headers))}{len(title_summary)+1}"
    adjust_columns(ws2)

    # ==============================================================================
    # SHEET 3: LOCATION PERFORMANCE (LOCATION-WISE REPORT)
    # ==============================================================================
    print("Writing Sheet 3: Location Performance...")
    ws3 = wb.create_sheet(title="Location Performance")
    ws3.views.sheetView[0].showGridLines = True
    ws3.freeze_panes = "A2"

    loc_headers = [
        'Job Location', 'City', 'State', 'Total Clicks', 'Unique Visitors (IPs)',
        'Total Jobs Posted', 'Active (Posted) Jobs', 'Expired (Removed) Jobs',
        'Jobs with Clicks', 'Zero-Click Jobs', '% Jobs with Clicks', 'Avg Clicks / Job',
        'First Click Date', 'Last Click Date', 'Performance Tier'
    ]
    loc_col_types = ['str', 'str', 'str', 'int', 'int', 'int', 'int', 'int', 'int', 'int', 'pct', 'float', 'date', 'date', 'status']

    write_table(ws3, 1, loc_headers, location_summary, loc_col_types, add_total=True, total_label="Total (All Locations)")
    ws3.auto_filter.ref = f"A1:{get_column_letter(len(loc_headers))}{len(location_summary)+1}"
    adjust_columns(ws3)

    # ==============================================================================
    # SHEET 4: TITLE_LOCATION_DAYWISE (DAY-WISE PERFORMANCE)
    # ==============================================================================
    print("Writing Sheet 4: Title + Location Day-Wise Performance...")
    ws4 = wb.create_sheet(title="Title_Location_Daywise")
    ws4.views.sheetView[0].showGridLines = True
    ws4.freeze_panes = "A2"

    combo_day_headers = [
        'Date', 'Job Title', 'Job Location', 'Job Status', 'Active Status',
        'Daily Clicks', 'Daily Unique IPs', 'Mobile Clicks', 'Desktop Clicks'
    ]
    combo_day_types = ['date', 'str', 'str', 'status', 'status', 'int', 'int', 'int', 'int']

    write_table(ws4, 1, combo_day_headers, combo_day_rows, combo_day_types, add_total=True, total_label="Total Daily Events")
    ws4.auto_filter.ref = f"A1:{get_column_letter(len(combo_day_headers))}{len(combo_day_rows)+1}"
    adjust_columns(ws4)

    # ==============================================================================
    # SHEET 5: TITLE_LOCATION_SUMMARY (COMBO OVERALL PERFORMANCE)
    # ==============================================================================
    print("Writing Sheet 5: Title + Location Summary...")
    ws5 = wb.create_sheet(title="Title_Location_Summary")
    ws5.views.sheetView[0].showGridLines = True
    ws5.freeze_panes = "A2"

    combo_headers = [
        'Job Title', 'Job Location', 'City', 'State', 'Current Inventory Status',
        'Total Jobs', 'Active (Posted) Jobs', 'Expired (Removed) Jobs', 'Total Clicks',
        'Unique Visitors (IPs)', 'Jobs with Clicks', 'Zero-Click Jobs',
        'First Click Date', 'Last Click Date', 'Performance Status'
    ]
    combo_types = ['str', 'str', 'str', 'str', 'status', 'int', 'int', 'int', 'int', 'int', 'int', 'int', 'date', 'date', 'status']

    write_table(ws5, 1, combo_headers, combo_summary, combo_types, add_total=True, total_label="Total Combinations")
    ws5.auto_filter.ref = f"A1:{get_column_letter(len(combo_headers))}{len(combo_summary)+1}"
    adjust_columns(ws5)

    # ==============================================================================
    # SHEET 6: JOBS_WITH_CLICKS (POSTED & EXPIRED STATUS OF JOBS WITH CLICKS)
    # ==============================================================================
    print("Writing Sheet 6: Jobs With Clicks (Posted & Expired Status)...")
    ws6 = wb.create_sheet(title="Jobs_With_Clicks")
    ws6.views.sheetView[0].showGridLines = True
    ws6.freeze_panes = "A2"

    jobs_click_headers = [
        'Job ID', 'Job Title', 'Location', 'City', 'State', 'Current Status',
        'Active Status', 'Date Posted', 'Valid Through', 'Total Clicks',
        'Unique Visitors (IPs)', 'Mobile Clicks', 'Desktop Clicks', 'Tablet Clicks',
        'First Click Timestamp', 'Last Click Timestamp', 'Job URL'
    ]
    jobs_click_types = ['str', 'str', 'str', 'str', 'str', 'status', 'status', 'date', 'date', 'int', 'int', 'int', 'int', 'int', 'date', 'date', 'str']

    write_table(ws6, 1, jobs_click_headers, jobs_with_clicks_rows, jobs_click_types, add_total=True, total_label="Total (Jobs with Clicks)")
    ws6.auto_filter.ref = f"A1:{get_column_letter(len(jobs_click_headers))}{len(jobs_with_clicks_rows)+1}"
    adjust_columns(ws6)

    # ==============================================================================
    # SHEET 7: ZERO_CLICK_JOBS (NON-PERFORMING INVENTORY)
    # ==============================================================================
    print("Writing Sheet 7: Zero Click Jobs (Non-Performing Inventory)...")
    ws7 = wb.create_sheet(title="Zero_Click_Jobs")
    ws7.views.sheetView[0].showGridLines = True
    ws7.freeze_panes = "A2"

    zero_headers = [
        'Job ID', 'Job Title', 'Location', 'City', 'State', 'Current Status',
        'Active Status', 'Date Posted', 'Valid Through', 'Total Clicks', 'Job URL'
    ]
    zero_types = ['str', 'str', 'str', 'str', 'str', 'status', 'status', 'date', 'date', 'int', 'str']

    write_table(ws7, 1, zero_headers, zero_click_jobs_rows, zero_types, add_total=False)
    ws7.auto_filter.ref = f"A1:{get_column_letter(len(zero_headers))}{len(zero_click_jobs_rows)+1}"
    adjust_columns(ws7)

    # ==============================================================================
    # SHEET 8: DAILY_TREND (DAY 1 TO TODAY)
    # ==============================================================================
    print("Writing Sheet 8: Daily Trend...")
    ws8 = wb.create_sheet(title="Daily_Trend")
    ws8.views.sheetView[0].showGridLines = True
    ws8.freeze_panes = "A2"

    trend_headers = [
        'Date', 'Day of Week', 'Daily Clicks', 'Daily Unique IPs', 'Cumulative Clicks',
        'Active Titles Clicked', 'Active Locations Clicked'
    ]
    trend_types = ['date', 'str', 'int', 'int', 'int', 'int', 'int']

    write_table(ws8, 1, trend_headers, daily_trend_rows, trend_types, add_total=True, total_label="Total / Overall")
    ws8.auto_filter.ref = f"A1:{get_column_letter(len(trend_headers))}{len(daily_trend_rows)+1}"
    adjust_columns(ws8)

    # ==============================================================================
    # SHEET 9: VISITOR_LOCATIONS (WHERE CLICKS ORIGINATED)
    # ==============================================================================
    print("Writing Sheet 9: Visitor Locations...")
    ws9 = wb.create_sheet(title="Visitor_Locations")
    ws9.views.sheetView[0].showGridLines = True
    ws9.freeze_panes = "A2"

    vloc_headers = ['Visitor City', 'Visitor State / Region', 'Visitor Country', 'Total Clicks', 'Unique IPs']
    vloc_types = ['str', 'str', 'str', 'int', 'int']

    write_table(ws9, 1, vloc_headers, visitor_loc_rows, vloc_types, add_total=True, total_label="Total Visitor Clicks")
    ws9.auto_filter.ref = f"A1:{get_column_letter(len(vloc_headers))}{len(visitor_loc_rows)+1}"
    adjust_columns(ws9)

    # Save workbooks
    file_name = f"{file_slug}_Clicks_Performance_Report.xlsx"
    antigravity_output = os.path.join(ANTIGRAVITY_DIR, file_name)
    artifact_output = os.path.join(ARTIFACT_DIR, file_name)

    print(f"Step 5: Saving workbook to {antigravity_output}...")
    wb.save(antigravity_output)
    shutil.copyfile(antigravity_output, artifact_output)

    file_size_kb = os.path.getsize(antigravity_output) / 1024
    print(f"Workbook successfully saved!")
    print(f" - Antigravity: {antigravity_output} ({file_size_kb:.2f} KB)")
    print(f" - Artifact: {artifact_output} ({file_size_kb:.2f} KB)")

    return {
        "client": client_name,
        "emp_id": emp_id,
        "total_jobs": len(jobs_dict),
        "posted_jobs": posted_jobs_cnt,
        "expired_jobs": expired_jobs_cnt,
        "total_clicks": len(click_records),
        "unique_ips": total_ips_count,
        "performing_jobs": len(job_clicks),
        "zero_click_jobs": len(zero_click_jobs_rows),
        "titles_count": len(title_summary),
        "locations_count": len(location_summary),
        "days_count": len(daily_trend_rows),
        "file_name": file_name,
        "antigravity_path": antigravity_output,
        "artifact_path": artifact_output,
        "size_kb": file_size_kb
    }


def main():
    configs = [
        {
            "emp_id": "6a7b516d060e8f0b78b0dc5a",
            "client_name": "QRM (Quality Rehab Management)",
            "file_slug": "QRM"
        },
        {
            "emp_id": "6aa8d214060e8f0b78b0dc87",
            "client_name": "ABS Kids",
            "file_slug": "ABS_Kids"
        }
    ]

    results = []
    for cfg in configs:
        res = generate_report_for_client(cfg["emp_id"], cfg["client_name"], cfg["file_slug"])
        results.append(res)

    print("\n" + "=" * 70)
    print("ALL REPORTS GENERATED SUCCESSFULLY:")
    for r in results:
        print(f"Client: {r['client']}")
        print(f"  Total Jobs: {r['total_jobs']:,} (Posted: {r['posted_jobs']:,}, Expired: {r['expired_jobs']:,})")
        print(f"  Google Clicks: {r['total_clicks']:,} | Unique Visitors (IPs): {r['unique_ips']:,}")
        print(f"  Performing Jobs: {r['performing_jobs']:,} | Zero-Click Jobs: {r['zero_click_jobs']:,}")
        print(f"  Saved File: {r['file_name']} ({r['size_kb']:.2f} KB)")
        print(f"  Paths:")
        print(f"    - {r['antigravity_path']}")
        print(f"    - {r['artifact_path']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
