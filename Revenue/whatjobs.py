import sys, os, re, logging, glob
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
# ===================== SETUP =====================
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SPREADSHEET_ID =os.getenv("WHATJOBS_SPREADSHEET_ID")
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
LOCAL_MONGO_URI = os.getenv("LOCAL_MONGO_URI", "mongodb://localhost:27017/")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
local_client = MongoClient(LOCAL_MONGO_URI)

# ⭐ FINAL DB NAME
local_db = local_client["whatjobs_revenue"]

# ===================== HELPERS =====================

def print_success(msg): print(f"\033[1;32m✔ {msg}\033[0m")
def print_error(msg): print(f"\033[1;31m✖ {msg}\033[0m")

def get_or_create_sheet(parent, name, rows=5000, cols=50):
    for ws in parent.worksheets():
        if ws.title.lower() == name.lower():
            return ws
    return parent.add_worksheet(title=name, rows=rows, cols=cols)

def load_domains(parent):
    ws = get_or_create_sheet(parent, "Domains")
    rows = ws.get_all_records()
    return [r["domain"] for r in rows if r.get("domain")]

def to_db_key(domain):
    return domain if domain.endswith("_prod") else domain.split(".")[0] + "_prod"

def clean_base_url(url):
    return "" if not url else url.split("?")[0]

def extract_jobid(url):
    if not url:
        return None
    url = str(url)
    m = re.search(r"_(\d{5,})__", url)
    if m:
        return str(int(m.group(1)))
    m = re.search(r"(\d{6,})", url)
    if m:
        return str(int(m.group(1)))
    return None

# ===================== WHATJOBS FETCH =====================

def fetch_views_for_domain(domain, uri, run_datetime):
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[domain]

        pipeline = [
            {"$match": {
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$gt": run_datetime},
                "$or": [
                    {"extraInfo.sourceEmployerId": {"$regex": "whatjobs", "$options": "i"}},
                    {"extraInfo.url": {"$regex": "^https://www\\.whatjobs\\.com", "$options": "i"}}
                ]
            }},
            {"$addFields": {"cleanUrl": {
                "$arrayElemAt": [{"$split": ["$extraInfo.url", "?"]}, 0]
            }}},
            {"$addFields": {
                "jobMatch": {
                    "$regexFind": {
                        "input": "$cleanUrl",
                        "regex": "___[0-9]+_([0-9]{5,})__"
                    }
                }
            }},
            {"$addFields": {
                "jobId": {
                    "$cond": [
                        {"$ne": ["$jobMatch", None]},
                        {"$arrayElemAt": ["$jobMatch.captures", 0]},
                        None
                    ]
                }
            }},
            {"$project": {
                "_id": 0,
                "company": 1,
                "jobId": 1,
                "cleanUrl": 1,
                "sourceEmployerId": "$extraInfo.sourceEmployerId"
            }}
        ]

        docs = list(db["userAnalytics"].aggregate(pipeline, allowDiskUse=True))
        print_success(f"{domain}: {len(docs)} WhatJobs views extracted")
        return [{"domain": domain, **d} for d in docs]

    except Exception as e:
        print_error(f"{domain} query failed: {e}")
        return []

# ===================== STATS ENGINE =====================

def compute_stats(run_date):
    rows = list(local_db["csv_matched"].find({}, {"_id": 0}))

    if not rows:
        print_error("NO matched rows for stats.")
        return None

    df = pd.DataFrame(rows)

    # 🔥 EXCLUDE UNMATCHED ROWS FROM STATS
    df = df[df["matched_domain"] != "UNMATCHED"]

    if df.empty:
        print_error("All rows were UNMATCHED — nothing to report")
        return pd.DataFrame()

    df["Client Billable"] = df.get("Client Billable", 0).astype(int)
    df["Cost"] = df.get("Cost", 0).astype(float)
    df["paid_revenue"] = df.apply(
        lambda r: r["Cost"] if r["Client Billable"] == 1 else 0,
        axis=1
    )

    stats = df.groupby(["matched_domain", "matched_company"]).agg(
        total=("jobId", "count"),
        paid_clicks=("Client Billable", lambda x: (x == 1).sum()),
        unpaid_clicks=("Client Billable", lambda x: (x == 0).sum()),
        paid_revenue=("paid_revenue", "sum")
    ).reset_index()

    stats.insert(0, "Date", run_date)
    stats = stats.sort_values(["matched_domain", "matched_company"]).reset_index(drop=True)

    return stats

def store_stats_in_mongo(run_date, stats, report_rows):
    record = {
        "run_date": run_date,
        "inserted_at": datetime.now(timezone.utc),  # Use timezone.utc
        "stats": stats.to_dict("records"),
        # "report": report_rows  <-- Reminder: Remove this to avoid the 16MB limit error
    }
    local_db["wj_stats"].insert_one(record)
    print_success("Stored stats → MongoDB.whatjobs_revenue.wj_stats")
# ===================== EXPORT (SMART UPDATE) =====================

def export_to_sheets(sheet, report_df, stats_df):

    if not sheet:
        print_error("Google Sheet handle is None. Cannot export.")
        return

    report_ws = get_or_create_sheet(sheet, "Report")
    report_ws.clear()
    report_ws.update(
        [report_df.columns.tolist()] +
        report_df.fillna("").astype(str).values.tolist()
    )

    stats_ws = get_or_create_sheet(sheet, "Stats")

    existing = stats_ws.get_all_records()
    df_existing = pd.DataFrame(existing) if existing else pd.DataFrame()

    if not df_existing.empty and "Date" in df_existing.columns:
        df_existing = df_existing[df_existing["Date"] != stats_df.iloc[0]["Date"]]

    df_final = pd.concat([df_existing, stats_df], ignore_index=True)

    stats_ws.clear()
    stats_ws.update(
        [df_final.columns.tolist()] +
        df_final.astype(str).values.tolist()
    )

    try:
        stats_ws.format("F2:F5000", {
            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"}
        })
    except Exception as e:
        print_error(f"Formatting error: {e}")

    print_success("Stats merged (append-or-update) → Google Sheets")

# ===================== MAIN =====================

def main():
    if len(sys.argv) < 2:
        print_error("Usage: python whatjobs_revenue.py 2025-12-01")
        sys.exit(1)

    run_date = sys.argv[1]
    run_datetime = datetime.strptime(run_date, "%Y-%m-%d")

    pattern = fr"C:\Users\JOBIAK\Downloads\Jobiak5 countryUnitedStates_{run_date}ClickWise*.csv"
    files = glob.glob(pattern)
    if not files:
        print_error("CSV not found.")
        sys.exit(1)

    csv_path = files[0]
    print_success(f"Using CSV → {csv_path}")

    df_csv = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df_csv["clean_url"] = df_csv["URL"].apply(clean_base_url)
    df_csv["jobId"] = df_csv["clean_url"].apply(extract_jobid)

    local_db["csv_raw"].drop()
    local_db["csv_raw"].insert_many(df_csv.to_dict("records"))

    sheet = gc.open_by_key(SPREADSHEET_ID)
    domains_raw = load_domains(sheet)
    db_keys = [to_db_key(d) for d in domains_raw]

    mongo_creds = {
        r["domain"]: r["mongo_uri"]
        for r in local_client["mongo_creds"]["creds"].find(
            {"domain": {"$in": db_keys}}, {"_id": 0}
        )
    }

    local_db["wj_views"].drop()

    with ThreadPoolExecutor(max_workers=20) as exe:
        futures = [
            exe.submit(fetch_views_for_domain, d, uri, run_datetime)
            for d, uri in mongo_creds.items()
        ]

        for f in as_completed(futures):
            docs = f.result()
            if docs:
                local_db["wj_views"].insert_many(docs)

    # ===================== MATCH LOGIC (UPDATED RULES) =====================
    views = {v["jobId"]: v for v in local_db["wj_views"].find({}, {"_id": 0})}
    output_rows = []

    for row in local_db["csv_raw"].find():
        jobid = row.get("jobId")
        match = views.get(jobid)
        company_name = row.get("Company Name", "").strip()

        if company_name:
            row["matched_domain"] = "UNMATCHED"
            row["matched_company"] = company_name
            row["matched_sourceEmployerId"] = ""
        else:
            if match:
                row["matched_domain"] = match.get("domain", "UNMATCHED")
                row["matched_company"] = match.get("company", "")
                row["matched_sourceEmployerId"] = match.get("sourceEmployerId", "")
            else:
                row["matched_domain"] = "UNMATCHED"
                row["matched_company"] = ""
                row["matched_sourceEmployerId"] = ""

        output_rows.append(row)

    local_db["csv_matched"].drop()
    local_db["csv_matched"].insert_many(output_rows)

    stats_df = compute_stats(run_date)

    store_stats_in_mongo(run_date, stats_df, output_rows)

    report_df = pd.DataFrame(output_rows)
    export_to_sheets(sheet, report_df, stats_df)

    print_success("🔥 WhatJobs Revenue Pipeline Completed")

if __name__ == "__main__":
    main()