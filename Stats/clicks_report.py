import sys
import io
import threading
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from dotenv import load_dotenv
import gspread
import smtplib
from pymongo import MongoClient
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from google.oauth2.service_account import Credentials

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

load_dotenv()

# ==========================================================
# CONFIG
# ==========================================================
LOCAL_MONGO_URI = os.getenv("MONGO_URI")
if not LOCAL_MONGO_URI:
    print("MONGO_URI not set in environment")
    sys.exit(1)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = os.getenv("SMTP_USER", "your-email@example.com")
SMTP_PASS = os.getenv("SMTP_PASS")

CREDENTIALS_FILE = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = "1jZX3nU-YqZiIoSyWDfzxzUyNMAQmo5EcN6LdQKYeXwc"
DOMAINS_SHEET = "Domains"
TEAMS_SHEET = "Teams"
SHEET_URL = (f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
             "/edit?usp=sharing")

TREND_DAYS = 7    # trend chart window
FETCH_DAYS = 8    # trend (7 days) + same weekday last week (day -7)

# Design tokens
GREEN = "#30d158"
GREEN_DARK = "#248a3d"
RED = "#ff453a"
RED_DARK = "#d70015"
INK = "#1d1d1f"
GREY = "#86868b"
GREY_LIGHT = "#aeaeb2"
GREY_FAINT = "#c7c7cc"
HAIRLINE = "#e8e8ed"
CARD_BG = "#f5f5f7"

# ==========================================================
# DATE ARG
# ==========================================================
if len(sys.argv) < 2:
    REPORT_DATE = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"No date provided. Defaulting to yesterday: {REPORT_DATE}")
else:
    REPORT_DATE = sys.argv[1]
MIN_DT = datetime.strptime(REPORT_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
MAX_DT = MIN_DT + timedelta(days=1)
REPORT_DT = MIN_DT
WINDOW_MIN_DT = MIN_DT - timedelta(days=FETCH_DAYS - 1)

# oldest -> newest, FETCH_DAYS long; last 7 are the trend window,
# and index 0 is the same weekday last week (for the WoW pill)
window_dates_all = [(REPORT_DT - timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(FETCH_DAYS - 1, -1, -1)]
window_dates = window_dates_all[-TREND_DAYS:]
WOW_DATE = window_dates_all[0]
REPORT_WEEKDAY = REPORT_DT.strftime("%a")      # e.g. "Tue"

day_letters = [
    datetime.strptime(dt, "%Y-%m-%d").strftime("%a")[0] for dt in window_dates
]

# ==========================================================
# HELPERS
# ==========================================================
def clean_domain(d: str) -> str:
    return (d or "").replace("https://", "").replace("http://", "").strip().strip("/")

def no_link(text: str) -> str:
    """Stop Gmail/Outlook auto-linking domain-like text (blue underline)."""
    return (text or "").replace(".", ".&#8203;").replace("/", "/&#8203;")

def to_int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0

def normalize_type(t) -> str:
    return str(t or "").strip().lower()

def is_true(v) -> bool:
    """Only true/TRUE (any case) counts. Blank / FALSE / anything else = off."""
    return str(v or "").strip().lower() == "true"

def pct_change(today: int, prev: int):
    if prev <= 0:
        return None
    return (today - prev) / prev * 100.0

def week_trend(values):
    """Chart direction: least-squares slope over the 7-day window,
    so one noisy day cannot flip the color of the week."""
    n = len(values)
    if n < 2:
        return True
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    slope = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    return slope >= 0

def fmt_signed(n: int) -> str:
    return f"+{n:,}" if n >= 0 else f"&#8722;{abs(n):,}"

def greeting_name(members, lead):
    """Personalized greeting from member first names.
    1 member -> 'Sai' ; 2 -> 'Sai & Priya' ; 3 -> 'Sai, Priya & Ravi' ;
    more (or no names) -> 'Team {lead}'."""
    firsts = [m[0].split()[0] for m in members if m and m[0]]
    if not firsts:
        return f"Team {lead}"
    if len(firsts) == 1:
        return firsts[0]
    if len(firsts) == 2:
        return f"{firsts[0]} &amp; {firsts[1]}"
    if len(firsts) == 3:
        return f"{firsts[0]}, {firsts[1]} &amp; {firsts[2]}"
    return f"Team {lead}"

# ----------------------------------------------------------
# Group By parsing. Sheet value examples:
#   "company" | "employerId" | "company,sourceEmployerId" | blank
# Blank -> default: company only.
# ----------------------------------------------------------
GROUP_FIELDS = {
    "company": ("By company", 0),
    "employerid": ("By employer ID", 1),
    "sourceemployerid": ("By source employer ID", 2),
}
DEFAULT_GROUPS = ["company"]

def parse_group_by(raw: str):
    fields = []
    for part in str(raw or "").split(","):
        key = part.strip().lower()
        if key in GROUP_FIELDS and key not in fields:
            fields.append(key)
    return fields or DEFAULT_GROUPS

# ==========================================================
# GOOGLE SHEETS (opened by ID)
# ==========================================================
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID)

domains_rows = sheet.worksheet(DOMAINS_SHEET).get_all_records()
teams_rows = sheet.worksheet(TEAMS_SHEET).get_all_records()

for r in domains_rows:
    r["Domain"] = (r.get("Domain") or "").strip()
    r["Database"] = (r.get("Database") or "").strip()   # optional column
    r["Domain Type"] = (r.get("Domain Type") or "").strip()
    r["EmployerId"] = (str(r.get("EmployerId") or "")).strip()
    r["Lead"] = (r.get("Lead") or "").strip()
    r["GroupBy"] = parse_group_by(r.get("Group By"))
    r["PostingsExpires"] = is_true(r.get("Postings & Expires"))

# Teams: Lead -> {"members": [(name, email), ...]}
teams = defaultdict(lambda: {"members": []})
for t in teams_rows:
    lead = (t.get("Lead") or "").strip()
    name = (t.get("User") or "").strip()
    email = (t.get("email") or t.get("Email") or "").strip()
    if lead and email:
        teams[lead]["members"].append((name, email))

# Lead -> [domain rows]
team_domains = defaultdict(list)
for r in domains_rows:
    if r["Domain"] and r["Lead"]:
        team_domains[r["Lead"]].append(r)

# Per-domain Group By config
domain_groups = {r["Domain"]: r["GroupBy"] for r in domains_rows if r["Domain"]}

# ==========================================================
# MONGO
# ==========================================================
client = MongoClient(LOCAL_MONGO_URI)
domains_col = client["mongo_creds"]["creds"]
stats_col = client["daily_domain_stats"]["stats"]

# ==========================================================
# DATABASE ROUTING BY DOMAIN TYPE
#   Proxy        -> prod_jobiak_ai
#   Direct Apply -> directclients_prod
#   Programmatic -> derived: strip extension, append _prod
#                   (earnwithwfh.com -> earnwithwfh_prod)
#   anything else -> optional "Database" column in the sheet
# ==========================================================
TYPE_DB_MAP = {
    "proxy": "prod_jobiak_ai",
    "direct apply": "directclients_prod",
    "direct_apply": "directclients_prod",
    "direct-apply": "directclients_prod",
}

# Index hints so Mongo never table-scans a week of userAnalytics
DB_HINTS = {
    "prod_jobiak_ai": "createdDt_1",
    "directclients_prod": "isBot_1_browser_1_country_1_createdDt_1_mapJobId_1",
}

def derive_prod_db(domain: str) -> str:
    """earnwithwfh.com -> earnwithwfh_prod"""
    host = clean_domain(domain).split("/")[0]
    if host.startswith("www."):
        host = host[4:]
    return host.split(".")[0] + "_prod"

def db_for(row) -> str:
    t = normalize_type(row.get("Domain Type"))
    if t == "programmatic":
        return derive_prod_db(row.get("Domain", ""))
    return TYPE_DB_MAP.get(t) or row.get("Database", "")

# Thread-safe Mongo client + creds caches
_client_cache = {}
_client_lock = threading.Lock()
_creds_cache = {}

def get_db(db_name):
    with _client_lock:
        record = _creds_cache.get(db_name)
        if record is None:
            record = domains_col.find_one({"domain": db_name})
            _creds_cache[db_name] = record or False
    if not record:
        return None
    uri = record["mongo_uri"]
    with _client_lock:
        c = _client_cache.get(uri)
        if c is None:
            c = MongoClient(uri, serverSelectionTimeoutMS=8000, maxPoolSize=20)
            _client_cache[uri] = c
    return c[db_name]

# ==========================================================
# FETCH VIEWS - full window (8 days), per-day rows.
# Captures company, employerId AND sourceEmployerId so any
# Group By combination from the sheet can be rendered.
# ==========================================================
def fetch_views(domain, db, db_name, employer_id, domain_type):
    col = db["userAnalytics"]
    match = {
        "isBot": False,
        "browserType": {"$ne": "Unknown"},
        "deviceType": {"$ne": "Unknown"},
        "isFromGoogle": True,
        "createdDt": {"$gt": WINDOW_MIN_DT, "$lt": MAX_DT},
    }
    if employer_id:
        match["employerId"] = employer_id

    pipeline = [
        {"$match": match},
        {"$project": {
            "Company": {"$ifNull": ["$company", {"$ifNull": ["$companyName", "Unknown"]}]},
            "date": {"$substr": ["$createdDt", 0, 10]},
            "employerId": {"$ifNull": ["$employerId", ""]},
            "url": 1,
            "submittedUrl": 1,
            "ipAddress": 1,
            "extraInfo": 1,
        }},
        {"$addFields": {
            "targetUrl": {"$ifNull": ["$url", {"$ifNull": ["$submittedUrl", ""]}]}
        }},
        {"$addFields": {
            "calculatedEndUrl": {
                "$ifNull": [
                    {"$arrayElemAt": [{"$split": ["$targetUrl", "/"]}, 2]},
                    ""
                ]
            }
        }},
        {"$addFields": {
            "sourceEmployerId": {
                "$ifNull": ["$extraInfo.sourceEmployerId", "$calculatedEndUrl"]
            }
        }},
        {"$group": {
            "_id": {
                "Company": "$Company",
                "EmployerId": "$employerId",
                "SourceEmployerId": "$sourceEmployerId",
                "Date": "$date",
            },
            "ViewsCount": {"$sum": 1},
            "UniqueIpCount": {"$addToSet": "$ipAddress"},
        }},
        {"$project": {
            "_id": 0,
            "Date": "$_id.Date",
            "Company": "$_id.Company",
            "EmployerId": {"$ifNull": ["$_id.EmployerId", ""]},
            "sourceEmployerId": {"$ifNull": ["$_id.SourceEmployerId", ""]},
            "ViewsCount": 1,
            "UniqueIpCount": {"$size": "$UniqueIpCount"},
            "Domain": domain,
            "Domain Type": domain_type,
        }},
    ]
    hint = DB_HINTS.get(db_name)
    if hint:
        try:
            return list(col.aggregate(pipeline, allowDiskUse=True, hint=hint))
        except Exception as e:
            print(f"  ! hint '{hint}' failed on {db_name} ({e}); retrying without hint")
    return list(col.aggregate(pipeline, allowDiskUse=True))

# ==========================================================
# POSTINGS & EXPIRES - only when "Postings & Expires" = TRUE.
# Report date only.
#   Proxy                       -> jobsGoogleSubmittedLog
#   Direct Apply / Programmatic -> aj_jp_google_logs (+ status_update: 6)
#   URL_UPDATED = postings, URL_DELETED = expires
# ==========================================================
def fetch_postings_expires(db, domain_type, employer_id):
    t = normalize_type(domain_type)
    if t == "proxy":
        col = db["jobsGoogleSubmittedLog"]
        match = {"createdAt": {"$gt": MIN_DT, "$lt": MAX_DT}}
    else:  # direct apply / programmatic
        col = db["aj_jp_google_logs"]
        match = {
            "createdAt": {"$gt": MIN_DT, "$lt": MAX_DT},
            "status_update": 6,
        }
    if employer_id:
        match["employerId"] = employer_id

    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$callType", "count": {"$sum": 1}}},
    ]
    postings = expires = 0
    for doc in col.aggregate(pipeline, allowDiskUse=True):
        if doc["_id"] == "URL_UPDATED":
            postings = to_int(doc["count"])
        elif doc["_id"] == "URL_DELETED":
            expires = to_int(doc["count"])
    return {"postings": postings, "expires": expires}

def process_domain(row):
    """Returns (domain, view_rows, postings_expires_or_None)."""
    domain = row["Domain"]
    domain_type = row["Domain Type"]
    employer_id = row["EmployerId"]
    if not domain:
        return (domain, [], None)

    db_name = db_for(row)
    if not db_name:
        print(f"  ! unknown Domain Type '{domain_type}' and no Database column for {domain} - skipping")
        return (domain, [], None)

    db = get_db(db_name)
    if db is None:
        print(f"  ! no mongo creds found for db '{db_name}' - skipping {domain}")
        return (domain, [], None)

    rows = fetch_views(domain, db, db_name, employer_id, domain_type)

    pe = None
    if row["PostingsExpires"]:
        try:
            pe = fetch_postings_expires(db, domain_type, employer_id)
        except Exception as e:
            print(f"  ! postings/expires failed for {domain}: {e}")

    return (domain, rows, pe)

# ==========================================================
# RUN STATS
# ==========================================================
stats_col.delete_many({"Date": REPORT_DATE})

all_rows = []
postings_expires = {}   # domain -> {"postings": n, "expires": n}
with ThreadPoolExecutor(max_workers=10) as ex:
    futures = [ex.submit(process_domain, r) for r in domains_rows]
    for f in as_completed(futures):
        domain, rows, pe = f.result()
        all_rows.extend(rows)
        if pe is not None:
            postings_expires[domain] = pe

today_rows = [r for r in all_rows if r.get("Date") == REPORT_DATE]

for r in today_rows:
    r["InsertedAt"] = datetime.now(timezone.utc)

if today_rows:
    stats_col.insert_many(today_rows)

# ==========================================================
# AGGREGATE TODAY (per-domain) - from today's rows only.
# rows keyed (company, employerId, sourceEmployerId)
# ==========================================================
domains = defaultdict(lambda: {
    "type": "",
    "clicks": 0,
    "ips": 0,
    "rows": defaultdict(lambda: {"clicks": 0, "ips": 0})
})

for r in domains_rows:
    dom = r["Domain"]
    if not dom:
        continue
    domains[dom]["type"] = r["Domain Type"]

for r in today_rows:
    dom = r.get("Domain", "")
    if not dom:
        continue
    d = domains[dom]
    d["type"] = r.get("Domain Type", d["type"])
    clicks = to_int(r.get("ViewsCount", 0))
    ips = to_int(r.get("UniqueIpCount", 0))
    d["clicks"] += clicks
    d["ips"] += ips
    key = (
        r.get("Company", "Unknown"),
        r.get("EmployerId", "") or "",
        r.get("sourceEmployerId", "") or "",
    )
    d["rows"][key]["clicks"] += clicks
    d["rows"][key]["ips"] += ips

# ==========================================================
# HISTORY - full fetched window (8 days). Last 7 feed the
# trend chart; day -7 feeds the per-domain WoW pill.
# ==========================================================
history = defaultdict(lambda: defaultdict(int))
for r in all_rows:
    history[r.get("Domain", "")][r.get("Date", "")] += to_int(r.get("ViewsCount", 0))

def series_for(domain):
    return [history.get(domain, {}).get(dt, 0) for dt in window_dates]

def wow_for(domain):
    """This domain today vs the same weekday last week."""
    today = history.get(domain, {}).get(REPORT_DATE, 0)
    prev = history.get(domain, {}).get(WOW_DATE, 0)
    return pct_change(today, prev)

# ==========================================================
# SMOOTH CHART PNG (Catmull-Rom smoothing)
# ==========================================================
def _catmull_rom(values, samples_per_seg=40):
    n = len(values)
    if n < 2:
        return list(range(n)), list(values)
    pts = [values[0]] + list(values) + [values[-1]]
    xs, ys = [], []
    for i in range(1, n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(samples_per_seg):
            t = s / samples_per_seg
            t2, t3 = t * t, t * t * t
            y = 0.5 * ((2 * p1) + (-p0 + p2) * t
                       + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                       + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            xs.append((i - 1) + t)
            ys.append(y)
    xs.append(n - 1)
    ys.append(values[-1])
    return xs, ys

def make_chart_png(values, rising: bool) -> bytes:
    color = GREEN if rising else RED
    xs, ys = _catmull_rom(values)

    fig, ax = plt.subplots(figsize=(5.2, 1.5), dpi=200)
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    ax.plot(xs, ys, color=color, linewidth=3, solid_capstyle="round", zorder=3)
    ax.fill_between(xs, ys, min(ys) - (max(ys) - min(ys) + 1) * 0.2,
                    color=color, alpha=0.14, linewidth=0, zorder=2)
    ax.scatter([len(values) - 1], [values[-1]], s=70, color=color,
               edgecolors="white", linewidths=2.2, zorder=4)

    lo, hi = min(values), max(values)
    pad = max((hi - lo) * 0.18, 1)
    ax.set_xlim(-0.05, len(values) - 0.8)
    ax.set_ylim(lo - pad, hi + pad)
    ax.axis("off")
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    return buf.getvalue()

# ==========================================================
# HTML PIECES
# ==========================================================
def day_strip_html(values, rising):
    accent = GREEN_DARK if rising else RED_DARK
    cells = ""
    n = len(values)
    for i, v in enumerate(values):
        if i < n - 1:
            cells += f"""
                <td align="center" width="14%" style="width:14%; padding:0 2px; text-align:center;"><div class="day-lbl" style="font-size:11px; color:{GREY_FAINT};">{day_letters[i]}</div><div class="day-val" style="font-size:12px; color:{GREY_LIGHT}; padding-top:4px; letter-spacing:-0.01em;">{v:,}</div></td>"""
        else:
            cells += f"""
                <td align="center" width="16%" style="width:16%; padding:0 2px; text-align:center;"><div class="day-lbl" style="font-size:11px; color:{accent}; font-weight:600;">Now</div><div class="day-val" style="font-size:12px; color:{INK}; font-weight:600; padding-top:4px; letter-spacing:-0.01em;">{v:,}</div></td>"""
    return f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; table-layout:fixed; margin-top:12px; margin-bottom:32px;">
                <tr>{cells}
                </tr>
            </table>"""

def section_html(title, mapping):
    if not mapping:
        return ""
    rows = ""
    for label, clicks in sorted(mapping.items(), key=lambda kv: kv[1], reverse=True):
        rows += f"""
                <tr>
                    <td class="row-lbl" style="font-size:14px; color:#6e6e73; padding:11px 0; border-top:1px solid {HAIRLINE};">{no_link(str(label))}</td>
                    <td class="row-val" align="right" style="text-align:right; font-size:14px; color:{INK}; padding:11px 0; border-top:1px solid {HAIRLINE};">{clicks:,}</td>
                </tr>"""
    return f"""
            <div class="sec-lbl" style="font-size:12px; font-weight:600; color:{GREY_LIGHT}; letter-spacing:0.06em; text-transform:uppercase; padding:26px 0 10px 0;">{title}</div>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;">{rows}
            </table>"""

def postings_expires_html(pe):
    if pe is None:
        return ""
    return f"""
            <div class="sec-lbl" style="font-size:12px; font-weight:600; color:{GREY_LIGHT}; letter-spacing:0.06em; text-transform:uppercase; padding:26px 0 10px 0;">Postings &amp; Expires</div>
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;">
                <tr>
                    <td class="row-lbl" style="font-size:14px; color:#6e6e73; padding:11px 0; border-top:1px solid {HAIRLINE};">Postings</td>
                    <td class="row-val" align="right" style="text-align:right; font-size:14px; color:{INK}; padding:11px 0; border-top:1px solid {HAIRLINE};">{pe['postings']:,}</td>
                </tr>
                <tr>
                    <td class="row-lbl" style="font-size:14px; color:#6e6e73; padding:11px 0; border-top:1px solid {HAIRLINE};">Expires</td>
                    <td class="row-val" align="right" style="text-align:right; font-size:14px; color:{INK}; padding:11px 0; border-top:1px solid {HAIRLINE};">{pe['expires']:,}</td>
                </tr>
            </table>"""

def receipt_rows_html(domain, d):
    """Group-by sections driven by the sheet's 'Group By' column.
    Blank -> default: By company only. Always followed by
    Total clicks + Unique visitors summary rows."""
    group_fields = domain_groups.get(domain, DEFAULT_GROUPS)

    sections = ""
    for field in group_fields:
        title, idx = GROUP_FIELDS[field]
        mapping = defaultdict(int)
        for key, s in d["rows"].items():
            label = key[idx]
            if field == "company" and (not label or label == "Unknown"):
                continue
            if field != "company" and not label:
                continue
            mapping[label] += s["clicks"]
        sections += section_html(title, mapping)

    summary = f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; margin-top:26px;">
                <tr>
                    <td class="row-lbl" style="font-size:14px; font-weight:600; color:{INK}; padding:12px 0; border-top:1px solid {HAIRLINE};">Total clicks</td>
                    <td class="row-val" align="right" style="text-align:right; font-size:14px; font-weight:600; color:{INK}; padding:12px 0; border-top:1px solid {HAIRLINE};">{d['clicks']:,}</td>
                </tr>
                <tr>
                    <td class="row-lbl" style="font-size:14px; font-weight:600; color:{INK}; padding:12px 0 0 0; border-top:1px solid {HAIRLINE};">Unique IPs</td>
                    <td class="row-val" align="right" style="text-align:right; font-size:14px; font-weight:600; color:{INK}; padding:12px 0 0 0; border-top:1px solid {HAIRLINE};">{d['ips']:,}</td>
                </tr>
            </table>"""

    return sections + summary

def domain_card_html(domain, d, values, chart_cid, rising, wow_pct):
    # Pill: this domain today vs the same weekday last week
    if wow_pct is None:
        pill = "&#8212;"
        pill_color = GREY
    else:
        arrow = "&#8593;" if wow_pct >= 0 else "&#8595;"
        pill = f"{arrow}&#8202;{abs(wow_pct):.1f}% vs last {REPORT_WEEKDAY}"
        pill_color = GREEN_DARK if wow_pct >= 0 else RED_DARK

    dtype = d.get("type") or ""
    chart_img = (
        f'<img src="cid:{chart_cid}" alt="7-day trend" width="520" '
        f'style="width:100%; height:auto; display:block;" />'
    ) if chart_cid else ""
    pe = postings_expires.get(domain)
    return f"""
        <tr><td class="card" style="background-color:{CARD_BG}; border-radius:26px; padding:32px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; margin-bottom:28px;">
                <tr>
                    <td valign="middle">
                        <div class="dom-name" style="font-size:15px; font-weight:600; color:{INK}; letter-spacing:-0.01em;">{no_link(clean_domain(domain))}</div>
                        <div style="font-size:13px; color:{GREY}; padding-top:3px;">{dtype}</div>
                    </td>
                    <td valign="middle" align="right" style="text-align:right;">
                        <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
                            <td class="pill" style="background-color:#ffffff; border-radius:100px; padding:6px 12px; font-size:12px; font-weight:600; color:{pill_color}; white-space:nowrap;">{pill}</td>
                        </tr></table>
                    </td>
                </tr>
            </table>
            <div class="big-num" style="font-size:52px; font-weight:300; color:{INK}; letter-spacing:-0.045em; line-height:0.95;">{d['clicks']:,}</div>
            <div style="font-size:14px; color:{GREY}; padding-top:12px; padding-bottom:26px;">clicks today</div>
            <div style="width:100%; line-height:0;">{chart_img}</div>
            {day_strip_html(values, rising)}
            {postings_expires_html(pe)}
            {receipt_rows_html(domain, d)}
        </td></tr>
        <tr><td style="height:20px; line-height:20px; font-size:0;">&nbsp;</td></tr>"""

# ==========================================================
# BUILD EMAIL FOR ONE TEAM
# Returns (html, [(cid, png_bytes), ...])
# ==========================================================
def build_team_email(lead, team_domain_rows, members, chart_offset=0):
    team_doms = [(r["Domain"], domains[r["Domain"]]) for r in team_domain_rows
                 if r["Domain"] in domains]
    ordered = sorted(team_doms, key=lambda x: x[1]["clicks"], reverse=True)
    if not ordered:
        return None, []

    total_today = sum(d["clicks"] for _, d in ordered)
    total_ips = sum(d["ips"] for _, d in ordered)

    daily_totals = [sum(series_for(dom)[i] for dom, _ in ordered)
                    for i in range(TREND_DAYS)]
    prev_totals = daily_totals[:-1]
    total_yesterday = prev_totals[-1] if prev_totals else 0
    delta = total_today - total_yesterday
    days_with_data = sum(1 for v in prev_totals if v > 0)

    # Headline: "best day" only if today STRICTLY beats real prior days
    if days_with_data == 0:
        headline, headline_color, arrow = "Here's how today went", GREY, "&#8226;"
    elif total_today > max(prev_totals) and total_today > 0:
        headline, headline_color, arrow = "Your best day this week", GREEN_DARK, "&#8593;"
    elif delta > 0:
        headline, headline_color, arrow = "Trending up today", GREEN_DARK, "&#8593;"
    elif delta < 0:
        headline, headline_color, arrow = "A slower day", RED_DARK, "&#8595;"
    else:
        headline, headline_color, arrow = "Holding steady", GREY, "&#8226;"

    images = []
    cards = ""
    for i, (dom, d) in enumerate(ordered):
        values = series_for(dom)
        rising = week_trend(values)
        wow = wow_for(dom)

        cid = None
        if any(values):
            cid = f"chart{chart_offset + i}"
            images.append((cid, make_chart_png(values, rising)))

        cards += domain_card_html(dom, d, values, cid, rising, wow)

    insight_block = f"""
        <tr><td class="darkcard" style="background-color:{INK}; border-radius:26px; padding:36px 30px 32px 30px;">
            <div style="font-size:13px; font-weight:600; color:{GREY}; padding-bottom:14px;">Grow this report</div>
            <div class="insight" style="font-size:21px; line-height:1.4; font-weight:500; color:#ffffff; letter-spacing:-0.018em;">
                Want more domains in tomorrow's report? Add them to the spreadsheet and they'll show up automatically.
            </div>
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:28px;"><tr>
                <td style="background-color:#ffffff; border-radius:100px;">
                    <a href="{SHEET_URL}" style="display:inline-block; padding:12px 26px; font-size:15px; font-weight:600; color:{INK}; text-decoration:none;">Add domains</a>
                </td>
            </tr></table>
        </td></tr>"""

    try:
        nice_date = REPORT_DT.strftime("%A, %B %-d")
    except ValueError:
        nice_date = REPORT_DT.strftime("%A, %B %d")

    html = f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="x-apple-disable-message-reformatting">
    <title>Daily clicks report</title>
    <style>
        /* Mobile: tighten every layer so nothing wraps or overflows */
        @media only screen and (max-width: 480px) {{
            .wrap    {{ padding: 0 10px !important; }}
            .card    {{ padding: 24px 18px !important; border-radius: 22px !important; }}
            .darkcard{{ padding: 28px 22px !important; border-radius: 20px !important; }}
            .hero-num{{ font-size: 64px !important; }}
            .hero-sub{{ font-size: 15px !important; }}
            .head-line{{ font-size: 14px !important; }}
            .big-num {{ font-size: 42px !important; }}
            .dom-name{{ font-size: 14px !important; }}
            .pill    {{ font-size: 10px !important; padding: 5px 9px !important; }}
            .stat-num{{ font-size: 17px !important; }}
            .stat-lbl{{ font-size: 10px !important; }}
            .day-lbl {{ font-size: 10px !important; }}
            .day-val {{ font-size: 10px !important; letter-spacing: -0.02em; }}
            .sec-lbl {{ font-size: 10px !important; padding-top: 20px !important; }}
            .row-lbl {{ font-size: 13px !important; padding-top: 9px !important; padding-bottom: 9px !important; }}
            .row-val {{ font-size: 13px !important; padding-top: 9px !important; padding-bottom: 9px !important; }}
            .insight {{ font-size: 18px !important; line-height: 1.45 !important; }}
        }}
    </style>
</head>
<body style="margin:0; padding:0; background-color:#ffffff; font-family:-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased;">
    <div style="display:none; max-height:0; overflow:hidden; mso-hide:all;">
        {total_today:,} clicks. {headline}.
    </div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; background-color:#ffffff;">
    <tr><td class="wrap" align="center" style="padding:0 20px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%; max-width:580px;">

        <tr><td align="center" style="padding:48px 0 0 0;">
            <div style="font-size:26px; font-weight:600; color:{INK}; letter-spacing:-0.02em;">Hey there &#128075;</div>
            <div class="head-line" style="font-size:15px; color:{GREY}; padding-top:10px;">Here's how your domains did on {nice_date}.</div>
        </td></tr>

        <tr><td align="center" style="padding:56px 0 0 0;">
            <div style="font-size:15px; font-weight:600; color:{headline_color}; padding-bottom:18px;">{arrow}&#8202; {headline}</div>
            <div class="hero-num" style="font-size:88px; font-weight:300; color:{INK}; letter-spacing:-0.05em; line-height:0.95;">{total_today:,}</div>
            <div class="hero-sub" style="font-size:16px; color:{GREY}; padding-top:16px;">clicks across your domains</div>
        </td></tr>

        <tr><td style="padding:56px 0 24px 0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;">
                <tr>
                    <td width="33%" align="center" style="width:33%; text-align:center; border-right:1px solid #f2f2f4; padding:4px 0;">
                        <div class="stat-num" style="font-size:22px; font-weight:500; color:{INK}; letter-spacing:-0.02em;">{fmt_signed(delta)}</div>
                        <div class="stat-lbl" style="font-size:13px; color:{GREY}; padding-top:6px;">vs Yesterday</div>
                    </td>
                    <td width="33%" align="center" style="width:33%; text-align:center; border-right:1px solid #f2f2f4; padding:4px 0;">
                        <div class="stat-num" style="font-size:22px; font-weight:500; color:{INK}; letter-spacing:-0.02em;">{total_ips:,}</div>
                        <div class="stat-lbl" style="font-size:13px; color:{GREY}; padding-top:6px;">Unique IPs</div>
                    </td>
                    <td width="34%" align="center" style="width:34%; text-align:center; padding:4px 0;">
                        <div class="stat-num" style="font-size:22px; font-weight:500; color:{INK}; letter-spacing:-0.02em;">{len(ordered)}</div>
                        <div class="stat-lbl" style="font-size:13px; color:{GREY}; padding-top:6px;">Domain{'s' if len(ordered) != 1 else ''} Tracked</div>
                    </td>
                </tr>
            </table>
        </td></tr>

        <tr><td style="height:48px; line-height:48px; font-size:0;">&nbsp;</td></tr>

{cards}
{insight_block}

        <tr><td align="center" style="padding:48px 0 60px 0;">
            <div style="font-size:12px; color:{GREY_LIGHT}; line-height:1.8;">
                Sent to Team {lead} by the Daily Click Report &middot; Delivered every morning
            </div>
        </td></tr>

    </table>
    </td></tr>
    </table>
</body>
</html>"""
    return html, images

# ==========================================================
# SEND - one email per team, all members in To
# ==========================================================
server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
server.login(SMTP_USER, SMTP_PASS)

chart_offset = 0
for lead, tdomains in team_domains.items():
    members = teams.get(lead, {}).get("members", [])
    if not members:
        print(f"! Team '{lead}' has domains but no members in Teams sheet - skipping")
        continue

    html, images = build_team_email(lead, tdomains, members, chart_offset)
    chart_offset += len(images)
    if html is None:
        print(f"! Team '{lead}' has no reportable domains - skipping")
        continue

    recipients = [email for _, email in members]

    msg = MIMEMultipart("related")
    msg["From"] = "Daily Clicks Report"
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"Daily Domain Click Report - Team {lead} - {REPORT_DATE}"

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html, "html"))
    msg.attach(alt)

    for cid, png in images:
        img = MIMEImage(png, _subtype="png")
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
        msg.attach(img)

    server.sendmail(SMTP_USER, recipients, msg.as_string())
    print(f"Sent Team {lead} report to: {', '.join(recipients)}")

server.quit()
print("All team reports sent.")