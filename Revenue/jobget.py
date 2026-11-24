import sys, os, re, logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# ===================== SETUP =====================
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SPREADSHEET_ID = os.getenv("JOBGET_GOOGLE_SHEET_ID")
CREDENTIALS_FILE = "credentials.json"
LOCAL_MONGO_URI = os.getenv("MONGO_URI")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

print("=================================================")
print(" GOOGLE SHEETS DEBUG INFO")
print(" Spreadsheet ID:", SPREADSHEET_ID)
print(" Credentials file:", CREDENTIALS_FILE)
print(" Service account email:", creds.service_account_email)
print("=================================================")

local_client = MongoClient(LOCAL_MONGO_URI)

# ===================== HELPERS =====================

def print_header(title):
    print(f"\n\033[1;36m=== {title} ===\033[0m")

def print_success(msg):
    print(f"\033[1;32m✔ {msg}\033[0m")

def print_warn(msg):
    print(f"\033[1;33m⚠ {msg}\033[0m")

def print_error(msg):
    print(f"\033[1;31m✖ {msg}\033[0m")

def get_or_create_worksheet(sheet, name, rows=300, cols=50):
    for ws in sheet.worksheets():
        if ws.title.lower().strip() == name.lower().strip():
            return ws
    return sheet.add_worksheet(title=name, rows=rows, cols=cols)

def clean_job_id(value):
    if value is None:
        return None
    s = str(value).strip()
    if s.startswith("'"):
        s = s[1:]
    s = re.sub(r"[^0-9]", "", s)
    return s if s else None

def normalize_minute(ts):
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M")
    try:
        return str(ts)[:16].replace("T", " ")
    except Exception:
        return None

def to_db_key(domain):
    v = str(domain).strip()
    if v.endswith("_prod"):
        return v
    if "." in v:
        return f"{v.split('.')[0]}_prod"
    return f"{v}_prod"

def load_domains(sheet):
    ws = get_or_create_worksheet(sheet, "Domains")
    data = ws.get_all_records()
    return [str(d.get("domain", "")).strip() for d in data if d.get("domain")]

def load_mongo_creds(domains):
    creds_col = local_client["mongo_creds"]["creds"]
    res = list(creds_col.find({"domain": {"$in": domains}}, {"_id": 0}))
    return {r["domain"]: {"uri": r["mongo_uri"], "db": r["domain"]} for r in res}

def safe_lower_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()

# ===================== IMPORT CPA + CPC REPORTS =====================

def import_all_reports(date_str):
    print_header("Importing CPA + CPC Reports")
    folder = os.path.join(os.path.expanduser("~"), "Downloads")

    candidates = [
        (f"click_events_publisher_664_on_{date_str}.csv", "CPA"),
        (f"click_events_publisher_664_on_{date_str}.csv.gz", "CPA"),
        (f"click_events_publisher_739_on_{date_str}.csv", "CPC"),
        (f"click_events_publisher_739_on_{date_str}.csv.gz", "CPC"),
    ]

    dfs = []
    for filename, rtype in candidates:
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            continue

        compression = "gzip" if filename.endswith(".gz") else None
        df = pd.read_csv(path, compression=compression, dtype=str, keep_default_na=False)

        if df.empty:
            continue

        df["report_type"] = rtype

        # Clean revenue columns (numeric)
        for c in df.columns:
            if any(k in c.lower() for k in ("revenue", "payout", "price")):
                df[c] = df[c].replace(r"[^0-9.\-]", "", regex=True)
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        # Normalize action_type early (prevents case bugs)
        if "action_type" in df.columns:
            df["action_type"] = safe_lower_series(df["action_type"])

        # Job ID
        job_col = next((c for c in df.columns if "job" in c.lower() and "id" in c.lower()), None)
        df["job_id_clean"] = df[job_col].apply(clean_job_id) if job_col else None

        df["date"] = date_str
        dfs.append(df)
        print_success(f"Loaded {len(df)} rows from {filename} ({rtype})")

    if not dfs:
        print_error("NO CPA or CPC files found!")
        sys.exit(1)

    out = pd.concat(dfs, ignore_index=True)

    # Guard: ensure report_type exists
    if "report_type" not in out.columns:
        print_error("report_type missing after import (this should never happen).")
        sys.exit(1)

    return out

# ===================== FETCH VIEWS =====================

def flatten_extra(doc):
    ei = doc.get("extraInfo") or {}
    doc["extraInfo.url"] = ei.get("url")
    doc["extraInfo.sourceEmployerId"] = ei.get("sourceEmployerId")
    return doc

def extract_api_job_id(*urls):
    for u in urls:
        if not u:
            continue
        u = str(u)

        m = re.search(r"/job/([\w\-]+)", u, re.I)
        if m:
            return clean_job_id(m.group(1))

        m = re.search(r"job[_-]?id=([\w\-]+)", u, re.I)
        if m:
            return clean_job_id(m.group(1))

        m = re.search(r"/viewjob/.*?([0-9]{6,})", u, re.I)
        if m:
            return clean_job_id(m.group(1))

    return None

def fetch_views(uri, db_name, date_str):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=4500)
        db = client[db_name]

        start = datetime.strptime(date_str, "%Y-%m-%d")
        end = start + timedelta(days=1, hours=6)

        projection = {
            "_id": 0,
            "ipAddress": 1,
            "company": 1,
            "createdDt": 1,
            "submittedUrl": 1,
            "extraInfo": 1
        }

        q1_cpa = {
            "isBot": False,
            "isFromGoogle": True,
            "createdDt": {"$gte": start, "$lt": end},
            "extraInfo.sourceEmployerId": "emp-gxc-jobgetcpa1"
        }

        q1_cpc = {
            "isBot": False,
            "isFromGoogle": True,
            "createdDt": {"$gte": start, "$lt": end},
            "extraInfo.sourceEmployerId": "emp-gxc-jobgetcpc1"
        }

        q2 = {
            "isBot": False,
            "isFromGoogle": True,
            "createdDt": {"$gte": start, "$lt": end},
            "extraInfo.url": {"$regex": "^https://job-api.jobget.com.*", "$options": "i"}
        }

        col = db["userAnalytics"]

        docs = list(col.find(q1_cpa, projection))
        docs += list(col.find(q1_cpc, projection))

        if not docs:
            docs = list(col.find(q2, projection))

        for d in docs:
            flatten_extra(d)
            d["domain"] = db_name
            d["apiJobId"] = clean_job_id(
                extract_api_job_id(d.get("extraInfo.url"), d.get("submittedUrl"))
            )
            d["trimmed_createdDt"] = normalize_minute(d.get("createdDt"))

        print_success(f"{db_name}: {len(docs)} views")
        return db_name, True, docs

    except Exception as e:
        print_error(f"{db_name}: error — {e}")
        return db_name, False, []

# ===================== STATS LOGIC (THE FIX) =====================

def normalize_paid(v):
    return str(v).strip().lower() in [
        "1", "true", "paid", "yes", "y", "jobget", "jobgetcpa1", "jobget_cpa"
    ]

def split_paid_unpaid(report_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits PAID vs UNPAID within a *given* report_df (CPA-only or CPC-only).
    This prevents CPA paid flags from impacting CPC, etc.
    """
    if report_df.empty:
        return report_df.copy(), report_df.copy()

    paid_mask = report_df.apply(
        lambda r: any(
            normalize_paid(r.get(c, "")) for c in report_df.columns if "paid" in c.lower()
        ),
        axis=1
    )
    paid_df = report_df[paid_mask].copy()
    unpaid_df = report_df[~paid_mask].copy()
    return paid_df, unpaid_df

def revenue_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if re.search(r"(revenue|payout|price)", c, re.I)]

def build_stats_for_report(report_df: pd.DataFrame, paid_df: pd.DataFrame, unpaid_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes per-domain stats ONLY from the provided report_df (CPA-only or CPC-only).
    No cross-contamination possible.
    """
    if report_df.empty:
        return pd.DataFrame(columns=[
            "Domain", "Paid Clicks", "Unpaid Clicks", "Paid Applies", "Unpaid Applies",
            "Paid Revenue ($)", "Unpaid Revenue ($)"
        ])

    rev_cols = revenue_columns(report_df)

    def get_clicks(df):
        if df.empty or "action_type" not in df.columns:
            return 0
        return int((safe_lower_series(df["action_type"]) == "click").sum())

    def get_applies(df):
        if df.empty or "action_type" not in df.columns:
            return 0
        return int((safe_lower_series(df["action_type"]) == "apply").sum())

    summary = []
    for domain in sorted(report_df["matched_domain"].dropna().unique()):
        p = paid_df[paid_df["matched_domain"] == domain]
        u = unpaid_df[unpaid_df["matched_domain"] == domain]

        paid_rev = float(p[rev_cols].sum().sum()) if (len(rev_cols) and len(p)) else 0.0
        unpaid_rev = float(u[rev_cols].sum().sum()) if (len(rev_cols) and len(u)) else 0.0

        summary.append({
            "Domain": domain,
            "Paid Clicks": get_clicks(p),
            "Unpaid Clicks": get_clicks(u),
            "Paid Applies": get_applies(p),
            "Unpaid Applies": get_applies(u),
            "Paid Revenue ($)": round(paid_rev, 2),
            "Unpaid Revenue ($)": round(unpaid_rev, 2),
        })

    return pd.DataFrame(summary)

def add_derived_columns(stats_df: pd.DataFrame, date: str) -> pd.DataFrame:
    if stats_df.empty:
        stats_df = stats_df.copy()
        stats_df["Total Clicks"] = 0
        stats_df["Revenue per Click ($)"] = 0
    else:
        stats_df = stats_df.copy()
        stats_df["Total Clicks"] = stats_df["Paid Clicks"] + stats_df["Unpaid Clicks"]
        stats_df["Revenue per Click ($)"] = (
            stats_df["Paid Revenue ($)"] + stats_df["Unpaid Revenue ($)"]
        ) / stats_df["Total Clicks"].replace(0, pd.NA)
        stats_df["Revenue per Click ($)"] = stats_df["Revenue per Click ($)"].fillna(0)

    ist_now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    stats_df["Last Updated (IST)"] = ist_now.strftime("%Y-%m-%d %H:%M:%S")
    stats_df["date"] = date
    return stats_df

# ===================== MAIN =====================

def main():
    if len(sys.argv) < 2:
        print_error("Usage: python jobget.py YYYY-MM-DD")
        sys.exit(1)

    date = sys.argv[1]
    sheet = gc.open_by_key(SPREADSHEET_ID)

    print_header(f"Running Jobget Pipeline for {date}")

    report = import_all_reports(date)

    raw = load_domains(sheet)
    db_names = [to_db_key(x) for x in raw]
    creds_map = load_mongo_creds(db_names)
    print_success(f"{len(creds_map)} domains loaded")

    # FETCH VIEWS
    all_views, stats_conn = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [
            ex.submit(fetch_views, creds_map[d]["uri"], creds_map[d]["db"], date)
            for d in creds_map
        ]
        for fut in as_completed(futures):
            dbn, ok, docs = fut.result()
            stats_conn.append((dbn, ok, len(docs)))
            all_views.extend(docs)

    if not all_views:
        print_error("No views found.")
        sys.exit(1)

    views = pd.DataFrame(all_views)

    # ============ WRITE SHEETS SAFELY ============
    def write_df(ws_name, df):
        ws = get_or_create_worksheet(sheet, ws_name)
        ws.clear()
        if df is None:
            df = pd.DataFrame()
        if df.empty:
            ws.update([["(no rows)"]])
            print_warn(f"Updated sheet → {ws_name} (empty)")
            return
        ws.update([df.columns.tolist()] + df.fillna("").astype(str).values.tolist())
        print_success(f"Updated sheet → {ws_name}")

    # Views
    write_df("Views", views)

    # Job matching
    if "apiJobId" not in views.columns:
        print_error("views missing apiJobId; cannot match report rows.")
        sys.exit(1)

    views["apiJobId"] = views["apiJobId"].apply(clean_job_id)

    # NOTE: if apiJobId repeats across domains, dict(zip(...)) keeps last seen.
    # Keeping your behavior but warning loudly.
    if views["apiJobId"].duplicated().any():
        dup_count = int(views["apiJobId"].duplicated().sum())
        print_warn(f"Detected {dup_count} duplicate apiJobId values in views; domain mapping may be overwritten.")

    view_domain_map = dict(zip(views["apiJobId"], views["domain"].astype(str)))
    view_company_map = dict(zip(views["apiJobId"], views["company"].astype(str)))

    report["job_id_clean"] = report["job_id_clean"].apply(clean_job_id)
    report["matched_domain"] = report["job_id_clean"].map(view_domain_map).fillna("UNMATCHED")
    report["company"] = report["job_id_clean"].map(view_company_map).fillna("")

    print_success("ID matching complete")

    # Split CPA/CPC (these are now the *source of truth* for stats)
    cpa_report = report[report["report_type"] == "CPA"].copy()
    cpc_report = report[report["report_type"] == "CPC"].copy()

    write_df("cpa_report", cpa_report)
    write_df("cpc_report", cpc_report)

    # Paid applies (still from full report, but you can split if you want)
    paid_all, unpaid_all = split_paid_unpaid(report)

    paid_applies = paid_all[safe_lower_series(paid_all.get("action_type", "")) == "apply"].copy()
    paid_applies["company"] = paid_applies["job_id_clean"].map(view_company_map).fillna("")
    write_df("Paid_Applies", paid_applies)

    # Domain connection stats
    domain_stats = pd.DataFrame(stats_conn, columns=["Domain", "Connected", "Views"])

    # ============ FIXED STATS SECTION ============
    # 1) Compute ALL stats (CPA + CPC combined) for Stats sheet
    stats_all = build_stats_for_report(report, paid_all, unpaid_all)
    stats_all = domain_stats.merge(stats_all, on="Domain", how="outer").fillna(0)
    stats_all = stats_all[(stats_all["Paid Clicks"] > 0) | (stats_all["Unpaid Clicks"] > 0)].copy()
    stats_all = add_derived_columns(stats_all, date)
    write_df("Stats", stats_all)

    # 2) Compute CPA stats ONLY from CPA data
    cpa_paid, cpa_unpaid = split_paid_unpaid(cpa_report)
    cpa_stats = build_stats_for_report(cpa_report, cpa_paid, cpa_unpaid)
    cpa_stats = domain_stats.merge(cpa_stats, on="Domain", how="outer").fillna(0)
    cpa_stats = cpa_stats[(cpa_stats["Paid Clicks"] > 0) | (cpa_stats["Unpaid Clicks"] > 0)].copy()
    cpa_stats = add_derived_columns(cpa_stats, date)
    write_df("cpa_stats", cpa_stats)

    # 3) Compute CPC stats ONLY from CPC data
    cpc_paid, cpc_unpaid = split_paid_unpaid(cpc_report)
    cpc_stats = build_stats_for_report(cpc_report, cpc_paid, cpc_unpaid)
    cpc_stats = domain_stats.merge(cpc_stats, on="Domain", how="outer").fillna(0)
    cpc_stats = cpc_stats[(cpc_stats["Paid Clicks"] > 0) | (cpc_stats["Unpaid Clicks"] > 0)].copy()
    cpc_stats = add_derived_columns(cpc_stats, date)
    write_df("cpc_stats", cpc_stats)

    # Optional: sanity warning if CPA/CPC look identical per-domain (often a smell)
    try:
        merged = cpa_stats.merge(
            cpc_stats,
            on="Domain",
            how="inner",
            suffixes=("_CPA", "_CPC")
        )
        if not merged.empty:
            metric_cols = [
                "Paid Clicks", "Unpaid Clicks", "Paid Applies", "Unpaid Applies",
                "Paid Revenue ($)", "Unpaid Revenue ($)", "Revenue per Click ($)"
            ]
            identical_domains = []
            for _, row in merged.iterrows():
                same = True
                for c in metric_cols:
                    if float(row[f"{c}_CPA"]) != float(row[f"{c}_CPC"]):
                        same = False
                        break
                if same:
                    identical_domains.append(row["Domain"])
            if identical_domains:
                print_warn(
                    "CPA and CPC stats are identical for these domains (could be legit, but usually suspicious): "
                    + ", ".join(map(str, identical_domains[:25]))
                    + (" ..." if len(identical_domains) > 25 else "")
                )
    except Exception:
        # never block pipeline on sanity check
        pass

    print_success("All sheets updated successfully!")
    print_header("Pipeline Complete")

if __name__ == "__main__":
    main()