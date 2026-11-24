"""
VyTalent Solutions - Expired Scraping Jobs Finder
=================================================

Process:
1. Connects to `prod_jobiak_ai.job` via dynamic credentials in `mongo_creds.creds`.
2. Queries all posted jobs for employerId `6a68fe0d060e8f0b78b0dc41` (VyTalent Solutions):
     db.job.find({"employerId": "6a68fe0d060e8f0b78b0dc41", "status": "posted"})
3. Extracts `clientJobId` for each posted job.
4. Checks `ETL_Scrapping_Data.ETL_Scraping_Data`:
     db.ETL_Scraping_Data.find({"clientJobId": clientJobId})
   - If present: ignore.
   - If NOT present: job has expired from scraping feed but remains active/posted in job collection.
5. Writes the missing jobs to the Google Spreadsheet:
   - Spreadsheet: https://docs.google.com/spreadsheets/d/1ZEZvEAjNFwPR-lQLe89y0IKIz_wmKios3yzscyYmYHY
   - Tab: `expired_scraping_jobs` (gid: 1749506053)
"""

import os
import sys
import argparse
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Load environment
load_dotenv()

# Defaults
DEFAULT_EMPLOYER_ID = "6a68fe0d060e8f0b78b0dc41"
DEFAULT_SPREADSHEET_ID = "1ZEZvEAjNFwPR-lQLe89y0IKIz_wmKios3yzscyYmYHY"
DEFAULT_TAB_NAME = "expired_scraping_jobs"
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")


def get_mongo_client():
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI not found in environment variables (.env)")
    return MongoClient(uri)


def get_remote_db(local_client, db_name: str):
    creds = local_client["mongo_creds"]["creds"].find_one(
        {"domain": db_name}, {"_id": 0, "mongo_uri": 1}
    )
    if not creds or "mongo_uri" not in creds:
        raise ValueError(f"No mongo_uri found in mongo_creds.creds for: {db_name}")
    client = MongoClient(creds["mongo_uri"])
    return client[db_name]


def get_gspread_client(creds_path: str = GOOGLE_CREDS_FILE):
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Google credentials file not found: {creds_path}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return gspread.authorize(creds)


def find_expired_scraping_jobs(local_client, employer_id: str):
    """
    Find posted jobs in prod_jobiak_ai.job whose clientJobId is absent
    from ETL_Scrapping_Data.ETL_Scraping_Data.
    """
    print(f"[*] Connecting to databases...")
    prod_db = get_remote_db(local_client, "prod_jobiak_ai")
    etl_db = get_remote_db(local_client, "ETL_Scrapping_Data")

    job_col = prod_db["job"]
    etl_col = etl_db["ETL_Scraping_Data"]

    print(f"[*] Querying posted jobs for employerId: {employer_id}...")
    posted_cursor = job_col.find(
        {"employerId": employer_id, "status": "posted"},
        {
            "jobId": 1,
            "clientJobId": 1,
            "title": 1,
            "location": 1,
            "url": 1,
            "submittedUrl": 1,
            "datePosted": 1,
            "validThrough": 1,
            "status": 1
        }
    )

    posted_jobs = list(posted_cursor)
    total_posted = len(posted_jobs)
    print(f"[+] Total posted jobs found: {total_posted}")

    if not posted_jobs:
        return []

    # Optimize lookup: query distinct clientJobIds in ETL_Scraping_Data for this employer
    print(f"[*] Querying active clientJobIds in ETL_Scraping_Data...")
    # Fetch all clientJobIds present in ETL_Scraping_Data for this employer
    active_etl_ids = set(etl_col.distinct("clientJobId", {"employerId": employer_id}))
    print(f"[+] Total distinct clientJobIds found in ETL_Scraping_Data: {len(active_etl_ids)}")

    # Double check missing candidates against ETL with strict find_one({"clientJobId": cjid})
    missing_jobs = []
    print(f"[*] Checking missing jobs against ETL_Scraping_Data...")
    
    for idx, job in enumerate(posted_jobs, start=1):
        cjid = job.get("clientJobId")
        if not cjid:
            continue
        
        # Quick filter against employer set
        if cjid in active_etl_ids:
            continue

        # If not in employer set, verify with global find_one as specified
        exists = etl_col.find_one({"clientJobId": cjid}, {"_id": 1})
        if not exists:
            missing_jobs.append(job)

        if idx % 1000 == 0:
            print(f"  Processed {idx}/{total_posted} posted jobs...")

    print(f"[+] Completed check: {len(missing_jobs)} jobs are missing from ETL_Scraping_Data.")
    return missing_jobs


def update_google_sheet(spreadsheet_id: str, tab_name: str, missing_jobs: list):
    """
    Write the missing jobs to the Google Spreadsheet tab.
    """
    print(f"[*] Authorizing with Google Sheets API...")
    gc = get_gspread_client()

    print(f"[*] Opening spreadsheet {spreadsheet_id}...")
    sh = gc.open_by_key(spreadsheet_id)

    # Get or create worksheet
    try:
        ws = sh.worksheet(tab_name)
        print(f"[+] Found worksheet: {tab_name}")
    except gspread.exceptions.WorksheetNotFound:
        print(f"[*] Worksheet '{tab_name}' not found. Creating it...")
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=20)

    # Prepare headers
    headers = [
        "clientJobId",
        "jobId",
        "title",
        "location",
        "url",
        "submittedUrl",
        "datePosted",
        "validThrough",
        "status"
    ]

    # Format rows
    rows_data = [headers]
    for j in missing_jobs:
        dt_posted = j.get("datePosted")
        if isinstance(dt_posted, datetime):
            dt_posted_str = dt_posted.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            dt_posted_str = str(dt_posted or "")

        dt_valid = j.get("validThrough")
        if isinstance(dt_valid, datetime):
            dt_valid_str = dt_valid.strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            dt_valid_str = str(dt_valid or "")

        row = [
            str(j.get("clientJobId", "")),
            str(j.get("jobId", "")),
            str(j.get("title", "")),
            str(j.get("location", "")),
            str(j.get("url", "")),
            str(j.get("submittedUrl", "")),
            dt_posted_str,
            dt_valid_str,
            str(j.get("status", ""))
        ]
        rows_data.append(row)

    print(f"[*] Clearing existing content in tab '{tab_name}'...")
    ws.clear()

    # Ensure sheet has enough rows and cols
    needed_rows = max(len(rows_data) + 10, 100)
    needed_cols = max(len(headers) + 2, 10)
    if ws.row_count < needed_rows or ws.col_count < needed_cols:
        ws.resize(rows=needed_rows, cols=needed_cols)

    print(f"[*] Writing {len(rows_data)} rows (including header) to '{tab_name}'...")
    ws.update(range_name=f"A1:I{len(rows_data)}", values=rows_data)
    print(f"[+] Successfully updated Google Sheet tab '{tab_name}' with {len(missing_jobs)} jobs!")


def main():
    parser = argparse.ArgumentParser(description="Find expired scraping jobs and export to Google Sheets")
    parser.add_argument("--employer-id", default=DEFAULT_EMPLOYER_ID, help="Employer ID (default: 6a68fe0d060e8f0b78b0dc41)")
    parser.add_argument("--sheet-id", default=DEFAULT_SPREADSHEET_ID, help="Google Spreadsheet ID")
    parser.add_argument("--tab", default=DEFAULT_TAB_NAME, help="Google Spreadsheet Tab Name (default: expired_scraping_jobs)")
    args = parser.parse_args()

    print("=" * 80)
    print("EXPIRED SCRAPING JOBS CHECKER")
    print(f"Employer ID    : {args.employer_id}")
    print(f"Spreadsheet ID : {args.sheet_id}")
    print(f"Target Tab     : {args.tab}")
    print("=" * 80)

    local_client = get_mongo_client()

    # 1. Find missing jobs
    missing_jobs = find_expired_scraping_jobs(local_client, args.employer_id)

    # 2. Write to Google Sheet
    if missing_jobs:
        update_google_sheet(args.sheet_id, args.tab, missing_jobs)
    else:
        print("[*] No missing jobs found. Nothing to write.")

    print("\n" + "=" * 80)
    print("PROCESS COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()
