import os
import time
from datetime import datetime, timedelta
import pandas as pd
from pymongo import MongoClient
import dateutil.parser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from dotenv import load_dotenv
load_dotenv()

# ================================================
# CONFIG
# ================================================
REMOTE_MONGO_URI = os.getenv("MONGO_URI")

SMTP_SENDER = os.getenv("SMTP_SENDER", "your-email@example.com")
SMTP_RECEIVER = os.getenv("SMTP_RECEIVER", "your-email@example.com")
SMTP_CC = os.getenv("SMTP_CC", "dev-team@example.com")
SMTP_APP_PASSWORD = os.getenv("SMTP_PASS")
SYNC_RETRY_MINUTES = 15
SYNC_MAX_RETRIES = 2

_DB_CLIENTS = {}


# ================================================
# SMTP EMAIL SENDER
# ================================================
def send_smtp_email(file_path, company, status, date, export_count):
    if not file_path or not os.path.exists(file_path):
        print("[WARN] Cannot send: CSV file missing.")
        return

    subject = f"{company} – {status} Export ({date})"
    body = f"""
Hi,

Your daily export for {company} is ready.

Type: {status}
Date: {date}
Jobs Exported: {export_count}

The CSV file is attached.
"""

    msg = MIMEMultipart()
    msg["From"] = SMTP_SENDER
    msg["To"] = SMTP_RECEIVER
    msg['Cc'] = SMTP_CC  # This displays the CC in the email header
    msg["Subject"] = subject
    msg.attach(MIMEText(body))

    # Attach CSV
    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(file_path)}"'
    )
    msg.attach(part)

    recipients = [SMTP_RECEIVER]
    if SMTP_CC:
        recipients.append(SMTP_CC)

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(SMTP_SENDER, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_SENDER, recipients, msg.as_string())
        server.quit()
        print("[OK] SMTP email sent successfully")

    except Exception as e:
        print("[ERROR] SMTP email error:", str(e))


# ================================================
# FETCH MONGO CREDS FOR JOBIAK DATABASES
# ================================================
def get_mongo_uri(domain_name):
    local_client = MongoClient(REMOTE_MONGO_URI)
    creds_col = local_client["mongo_creds"]["creds"]

    doc = creds_col.find_one({"domain": domain_name}, {"_id": 0, "mongo_uri": 1})
    if not doc:
        raise Exception("No mongo_uri found for domain: " + domain_name)

    print(f"[OK] Loaded mongo_uri for {domain_name}")
    return doc["mongo_uri"]


def get_db(domain):
    if domain not in _DB_CLIENTS:
        _DB_CLIENTS[domain] = MongoClient(get_mongo_uri(domain))
    return _DB_CLIENTS[domain]


# ================================================
# EXPORT CSV
# ================================================
def export_csv(data, company, status):
    if not data:
        print("[WARN] No data to export.")
        return None

    df = pd.DataFrame(data)

    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    folder = os.path.join(downloads, "Proxy CSV's", status)
    os.makedirs(folder, exist_ok=True)

    today = datetime.today()
    filename = f"{company}_{status}_{today.strftime('%b')}_{today.strftime('%d')}.csv"
    full_path = os.path.join(folder, filename)

    df.to_csv(full_path, index=False)
    print("[OK] Exported:", full_path)

    return full_path


# ================================================
# 5K CUT-OFF
# ================================================
def pick_2500_cutoff(results):
    total = 0
    for r in results:
        total += r["count"]
        if total >= 2500:
            return r["date"]
    return results[-1]["date"] if results else None


# ================================================
# LOGGING
# ================================================
def log_run(col, doc):
    from datetime import timezone
    doc["createdAt"] = datetime.now(timezone.utc)
    col.insert_one(doc)


def already_exported(col, employer_id, status, date):
    return col.find_one({
        "EmployerId": employer_id,
        "Status": status,
        "date": date,
        "exportDone": True
    })


# ================================================
# SYNC CHECK
# ================================================
def check_sync(etl_db, logs, emp, company, status):
    today = datetime.today().strftime("%Y-%m-%d")
    last_summary = []

    for attempt in range(1, SYNC_MAX_RETRIES + 1):
        print(f"[SYNC] Check attempt {attempt} for {company} ({status})")

        pipeline = [
            {"$match": {"employerId": emp}},
            {"$addFields": {"date": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$updatetime"}
            }}},
            {"$group": {"_id": {"date": "$date"}, "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "date": "$_id.date", "count": 1}},
            {"$sort": {"date": 1}},
        ]

        results = list(etl_db.aggregate(pipeline))
        last_summary = results

        print("[INFO] Summary:", results)

        has_today = any(r["date"] == today and r["count"] > 0 for r in results)

        log_run(logs, {
            "EmployerId": emp,
            "Company": company,
            "Status": status,
            "type": "sync_check",
            "date": today,
            "attempt": attempt,
            "scrapingSummary": results,
            "syncStatus": "ok" if has_today else "no_today"
        })

        if has_today:
            print("[OK] Sync OK")
            return True, results

        print("[WARN] Missing today. Retrying in 15 mins...")
        if attempt < SYNC_MAX_RETRIES:
            time.sleep(SYNC_RETRY_MINUTES * 60)

    print("[ERROR] Sync failed.")
    return False, last_summary


# ================================================
# POSTINGS WORKFLOW
# ================================================
def handle_postings(emp, company, etl_db, job_db, logs):
    today = datetime.today().strftime("%Y-%m-%d")

    sync_ok, summary = check_sync(etl_db, logs, emp, company, "Postings")
    if not sync_ok:
        log_run(logs, {
            "EmployerId": emp,
            "Company": company,
            "Status": "Postings",
            "date": today,
            "exportDone": False,
            "reason": "sync_failed"
        })
        return

    start = datetime.strptime(today, "%Y-%m-%d")
    end = start + timedelta(days=1)

    etl_ids = {
        d["clientJobId"]
        for d in etl_db.find(
            {"employerId": emp, "updatetime": {"$gte": start, "$lt": end}},
            {"_id": 0, "clientJobId": 1}
        ) if "clientJobId" in d
    }

    job_ids = {
        d["clientJobId"]
        for d in job_db.find(
            {"employerId": emp},
            {"_id": 0, "clientJobId": 1}
        ) if "clientJobId" in d
    }

    missing = sorted(list(etl_ids - job_ids))[:2500]
    csv_data = [{"clientJobId": x} for x in missing]

    csv_path = export_csv(csv_data, company, "Postings")
    export_count = len(missing)

    if csv_path and export_count:
        send_smtp_email(csv_path, company, "Postings", today, export_count)

    log_run(logs, {
        "EmployerId": emp,
        "Company": company,
        "Status": "Postings",
        "date": today,
        "syncSummary": summary,
        "exportCount": export_count,
        "exportDone": True if csv_path else False
    })


# ================================================
# UPDATES WORKFLOW
# ================================================
def handle_updates(emp, company, job_db, logs):
    today = datetime.today().strftime("%Y-%m-%d")

    pipeline = [
        {"$match": {
            "employerId": emp,
            "status": "posted",
            "isActive": True,
            "datePosted": {"$exists": True},
            "title": {"$nin": [
                "Online Survey Taker",
                "Online Survey Taker - Earn up to $1K every month",
                "Survey Taker"
            ]}
        }},
        {"$addFields": {
            "date": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$validThrough"}
            }
        }},
        {"$group": {"_id": {"date": "$date"}, "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "date": "$_id.date", "count": 1}},
        {"$sort": {"date": 1}},
    ]

    results = list(job_db.aggregate(pipeline))
    cutoff = pick_2500_cutoff(results)

    if not cutoff:
        log_run(logs, {
            "EmployerId": emp,
            "Company": company,
            "Status": "Updates",
            "date": today,
            "exportDone": False,
            "reason": "no_jobs"
        })
        return

    cutoff_dt = dateutil.parser.parse(cutoff + "T00:00:00Z")
    end_window = cutoff_dt + timedelta(days=1)

    jobs = list(
        job_db.find(
            {
                "employerId": emp,
                "status": "posted",
                "isActive": True,
                "datePosted": {"$exists": True},
                "validThrough": {"$lt": end_window},
                "title": {"$nin": [
                    "Online Survey Taker",
                    "Online Survey Taker - Earn up to $1K every month",
                    "Survey Taker"
                ]}
            },
            {"_id": 0, "jobId": 1}
        )
    )[:5000]

    export_count = len(jobs)
    csv_path = export_csv(jobs, company, "Updates")

    if csv_path and export_count:
        send_smtp_email(csv_path, company, "Updates", today, export_count)

    log_run(logs, {
        "EmployerId": emp,
        "Company": company,
        "Status": "Updates",
        "date": today,
        "cutoff": cutoff,
        "exportCount": export_count,
        "exportDone": True if csv_path else False
    })


# ================================================
# MAIN
# ================================================
def main():
    proxy_conn = get_db("proxy_stats")
    logs = proxy_conn["proxy_stats"]["run_logs"]
    configs = list(proxy_conn["proxy_stats"]["config"].find({}))

    today = datetime.today().strftime("%Y-%m-%d")

    print(f"[INFO] Loaded {len(configs)} config rows")

    for row in configs:
        emp = row["EmployerId"]
        status = row["Status"]
        company = row["Company"]

        print(f"\n[INFO] Processing {company} ({status})")

        if already_exported(logs, emp, status, today):
            print("[SKIP] Already exported today, skipping.")
            continue

        if status == "Postings":
            etl_db = get_db("ETL_Scrapping_Data")["ETL_Scrapping_Data"]["ETL_Scraping_Data"]
            job_db = get_db("prod_jobiak_ai")["prod_jobiak_ai"]["job"]
            handle_postings(emp, company, etl_db, job_db, logs)

        elif status == "Updates":
            job_db = get_db("prod_jobiak_ai")["prod_jobiak_ai"]["job"]
            handle_updates(emp, company, job_db, logs)

        else:
            print("[ERROR] Unknown status:", status)


# ================================================
# RUN
# ================================================
if __name__ == "__main__":
    main()