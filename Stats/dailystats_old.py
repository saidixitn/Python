import sys
sys.stdout.reconfigure(line_buffering=True)

from pymongo import MongoClient
from pymongo.errors import OperationFailure
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import threading
import traceback
import os
import time
from dotenv import load_dotenv

load_dotenv(r"./.env")

# =========================================================
# LOCAL CONNECTION
# =========================================================

LOCAL_MONGO_URI = os.getenv("MONGO_URI")
local_client = MongoClient(LOCAL_MONGO_URI)

# =========================================================
# DAILY STATS DB & OLDSTATS COLLECTION
# =========================================================

daily_stats_db = local_client["daily_stats"]
input_col = daily_stats_db["input"]
oldstats_col = daily_stats_db["oldstats"]

# =========================================================
# CREDS DB
# =========================================================

creds_db = local_client["mongo_creds"]
creds_col = creds_db["creds"]

# =========================================================
# CACHE & THREADING
# =========================================================

DB_CACHE = {}
CLIENT_CACHE = {}
CACHE_LOCK = threading.Lock()

MAX_WORKERS = 3  # 3 concurrent domains keeps database load light and smooth

# =========================================================
# DATE RANGE: 2026-08-01 to 2026-11-05 (inclusive)
# =========================================================

UTC = timezone.utc

START_DATE = datetime(2026, 8, 1, tzinfo=UTC)
END_DATE = datetime(2026, 11, 5, tzinfo=UTC)

def generate_date_range(start_dt, end_dt):
    current = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    dates = []
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates

# =========================================================
# GET DATABASE (by name)
# =========================================================

def get_database_by_name(db_name):
    try:
        if db_name in DB_CACHE:
            return DB_CACHE[db_name]

        with CACHE_LOCK:
            if db_name in DB_CACHE:
                return DB_CACHE[db_name]

            creds = creds_col.find_one(
                {"domain": db_name},
                {"_id": 0, "mongo_uri": 1}
            )

            if not creds or "mongo_uri" not in creds:
                print(f"Mongo URI not found for {db_name}")
                return None

            client = MongoClient(creds["mongo_uri"], maxPoolSize=50)
            db = client[db_name]

            CLIENT_CACHE[db_name] = client
            DB_CACHE[db_name] = db

            print(f"CONNECTED : {db_name}")
            return db

    except Exception:
        print(traceback.format_exc())
        return None

# =========================================================
# GET DATABASE (by domain / domain type)
# =========================================================

def get_database(domain, domain_type):
    if domain_type == "Proxy":
        db_name = "prod_jobiak_ai"
    elif domain_type == "Direct Apply":
        db_name = "directclients_prod"
    elif domain_type == "Programmatic":
        base_domain = domain.replace("www.", "").split(".")[0]
        db_name = f"{base_domain}_prod"
    else:
        return None

    return get_database_by_name(db_name)

# =========================================================
# HELPERS
# =========================================================

def normalize_employer_ids(employer_id):
    if employer_id is None:
        return []

    if isinstance(employer_id, str):
        employer_ids = [employer_id]
    elif isinstance(employer_id, (list, tuple, set)):
        employer_ids = list(employer_id)
    else:
        employer_ids = [employer_id]

    return list(dict.fromkeys(
        str(value).strip()
        for value in employer_ids
        if value is not None and str(value).strip()
    ))


def build_employer_filter(domain_type, employer_ids):
    if domain_type == "Programmatic":
        return {}
    return {"employerId": {"$in": employer_ids}}


COMPANY_NAME_FIELDS = ["company", "companyName", "hiringOrganization.name", "employerName"]


def resolve_company_name(input_company, jobs_col, employer_ids):
    name = (input_company or "").strip()
    if name:
        return name

    if not employer_ids:
        return ""

    try:
        projection = {"_id": 0, **{f: 1 for f in COMPANY_NAME_FIELDS}}
        doc = jobs_col.find_one(
            {"employerId": {"$in": employer_ids}},
            projection
        )
        if not doc:
            return ""

        for field in COMPANY_NAME_FIELDS:
            value = doc
            for part in field.split("."):
                value = value.get(part) if isinstance(value, dict) else None
                if value is None:
                    break
            if isinstance(value, str) and value.strip():
                return value.strip()
    except Exception:
        pass

    return ""

# =========================================================
# PROCESS A SINGLE DOMAIN (LOG-BASED HISTORICAL STATS)
# =========================================================

def process_domain(domain_doc, dates):
    domain = domain_doc.get("Domain")
    domain_type = domain_doc.get("DomainType")
    raw_employer_id = domain_doc.get("employerId")
    employer_ids = normalize_employer_ids(raw_employer_id)
    input_company = str(domain_doc.get("Company", "") or "").strip()

    if domain_type in ("Proxy", "Direct Apply") and not employer_ids:
        print(f"SKIPPED : No employerId found for {domain}")
        return False, domain, 0

    db = get_database(domain, domain_type)
    if db is None:
        print(f"DB NOT FOUND for {domain}")
        return False, domain, 0

    t_start = time.time()
    print(f"[{domain}] Starting processing for {len(dates)} dates ({START_DATE.date()} -> {END_DATE.date()})...")

    # Select collections
    if domain_type == "Proxy":
        jobs_col = db["job"]
        analytics_col = db["userAnalytics"]
        logs_col = db["jobsGoogleSubmittedLog"]
        id_field = "childJobId"
        is_proxy = True
    else:
        jobs_col = db["Target_P4_Opt"]
        analytics_col = db["userAnalytics"]
        logs_col = db["aj_jp_google_logs"]
        id_field = "jobPubJobId"
        is_proxy = False

    company_name = resolve_company_name(input_company, jobs_col, employer_ids)
    base_filter = build_employer_filter(domain_type, employer_ids)

    # 1. Initial cumulative totals before START_DATE
    initial_posted = logs_col.count_documents({
        **base_filter,
        "callType": "URL_UPDATED",
        "createdAt": {"$lt": START_DATE}
    })
    initial_expired = logs_col.count_documents({
        **base_filter,
        "callType": "URL_DELETED",
        "createdAt": {"$lt": START_DATE}
    })

    # 2. Fetch all Google logs in the entire historical window [START_DATE, END_DATE + 1 day)
    window_end_max = END_DATE + timedelta(days=1)
    logs_query = {
        **base_filter,
        "createdAt": {"$gte": START_DATE, "$lt": window_end_max}
    }
    log_projection = {"_id": 0, "jobId": 1, "callType": 1, "createdAt": 1}
    all_logs = list(logs_col.find(logs_query, log_projection))

    # Partition logs by UTC day
    logs_by_date = {}
    for l in all_logs:
        dt = l.get("createdAt")
        if not dt:
            continue
        dt_utc = dt.replace(tzinfo=UTC if not dt.tzinfo else None)
        day_key = dt_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        logs_by_date.setdefault(day_key, []).append(l)

    # 3. Pre-aggregate DB_Clicks and Bot_Visits across the 3-month window for this employer
    # This reduces 194 heavy queries into just 2 fast aggregations!
    analytics_filter = {"employerId": {"$in": employer_ids}} if employer_ids else {}

    # Batch Bot Visits
    bot_pipeline = [
        {"$match": {**analytics_filter, "isBot": True, "createdDt": {"$gte": START_DATE, "$lt": window_end_max}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}}, "count": {"$sum": 1}}}
    ]
    bot_counts_by_day = {
        r["_id"]: r["count"]
        for r in analytics_col.aggregate(bot_pipeline, allowDiskUse=True)
    }

    # Batch DB Clicks
    clicks_pipeline = [
        {
            "$match": {
                **analytics_filter,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$gte": START_DATE, "$lt": window_end_max}
            }
        },
        {
            "$group": {
                "_id": {
                    "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}},
                    "ip": "$ipAddress",
                    "job": f"${'jobId' if is_proxy else 'jobPubJobId'}"
                }
            }
        },
        {
            "$group": {
                "_id": "$_id.day",
                "count": {"$sum": 1}
            }
        }
    ]
    clicks_counts_by_day = {
        r["_id"]: r["count"]
        for r in analytics_col.aggregate(clicks_pipeline, allowDiskUse=True)
    }

    # Pre-fetch removed clientJobIds to fast-check reposts (Proxy only)
    removed_client_ids = set()
    if is_proxy:
        removed_client_ids = set(jobs_col.distinct("clientJobId", {
            "employerId": {"$in": employer_ids},
            "status": "removed"
        }))

    # 4. Iterate dates sequentially maintaining exact cumulative counts
    cum_posted = initial_posted
    cum_expired = initial_expired
    docs_to_insert = []

    for dt in dates:
        dt_str = dt.strftime("%Y-%m-%d")
        w_start = dt
        w_end = dt + timedelta(days=1)
        window = {"$gte": w_start, "$lt": w_end}

        day_logs = logs_by_date.get(dt, [])
        updated_logs = [l for l in day_logs if l.get("callType") == "URL_UPDATED"]
        deleted_logs = [l for l in day_logs if l.get("callType") == "URL_DELETED"]

        day_updated_count = len(updated_logs)
        day_expired_count = len(deleted_logs)

        # Cumulative totals as of the end of the day window
        cum_posted += day_updated_count
        cum_expired += day_expired_count

        postings = updates = reposts = 0
        posted_ids = []
        expired_ids = [l["jobId"] for l in deleted_logs if l.get("jobId")]

        # Classify URL_UPDATED jobs for this day
        if day_updated_count > 0:
            candidate_job_ids = [l["jobId"] for l in updated_logs if l.get("jobId")]

            # Jobs that had prior URL_UPDATED logs before w_start are 'updates'
            prior_logged_ids = set(logs_col.distinct("jobId", {
                **base_filter,
                "jobId": {"$in": candidate_job_ids},
                "callType": "URL_UPDATED",
                "createdAt": {"$lt": w_start}
            }))

            if is_proxy:
                job_cids = {
                    j["jobId"]: j.get("clientJobId")
                    for j in jobs_col.find({"jobId": {"$in": candidate_job_ids}}, {"jobId": 1, "clientJobId": 1})
                }
                for jid in candidate_job_ids:
                    if jid in prior_logged_ids:
                        updates += 1
                    else:
                        cid = job_cids.get(jid)
                        if cid and cid in removed_client_ids:
                            reposts += 1
                        else:
                            postings += 1
                    posted_ids.append(jid)
            else:
                for jid in candidate_job_ids:
                    if jid in prior_logged_ids:
                        updates += 1
                    else:
                        postings += 1
                    posted_ids.append(jid)

        # Bot visits and DB clicks from pre-aggregated batch maps
        bot_visits = bot_counts_by_day.get(dt_str, 0)
        db_clicks = clicks_counts_by_day.get(dt_str, 0)

        # Posted Bot (excluding cache-updated jobs: posted_ids only contains Google-submitted jobs)
        if posted_ids:
            bot_match = {
                id_field: {"$in": posted_ids},
                "isBot": True,
                "createdDt": window
            }
            if is_proxy:
                bot_match["country"] = "United States"
            else:
                bot_match["action"] = {"$in": ["post", "repost", "update"]}
            posted_bot = len(analytics_col.distinct(id_field, bot_match))
        else:
            posted_bot = 0

        # Expires Bot
        if expired_ids:
            exp_bot_match = {
                id_field: {"$in": expired_ids},
                "isBot": True,
                "createdDt": window
            }
            if is_proxy:
                exp_bot_match["country"] = "United States"
            else:
                exp_bot_match["action"] = "expire"
            expires_bot = len(analytics_col.distinct(id_field, exp_bot_match))
        else:
            expires_bot = 0

        # Build output document (To_Expire_In_5Days, To_Post, FeedExpiredJobs removed as requested)
        doc = {
            "Domain": domain,
            "DomainType": domain_type,
            "employerId": raw_employer_id,
            "Date": dt,
            "WindowStart": w_start,
            "WindowEnd": w_end,
            "GeneratedAt": datetime.now(UTC),
            "Posted_Jobs": postings,
            "Updated_Jobs": updates,
            "Reposts": reposts,
            "Cache_Updated_Jobs": 0,
            "Expired_Jobs": day_expired_count,
            "Posted_Bot": posted_bot,
            "Expires_Bot": expires_bot,
            "DB_Clicks": db_clicks,
            "Bot_Visits": bot_visits,
            "Total_Posted_Jobs": cum_posted,
            "Total_Expired_Jobs": cum_expired
        }
        if company_name:
            doc["Company"] = company_name

        docs_to_insert.append(doc)

    # Bulk upsert all 97 documents for this domain
    for d in docs_to_insert:
        oldstats_col.update_one(
            {"Domain": d["Domain"], "Date": d["Date"]},
            {"$set": d},
            upsert=True
        )

    t_elapsed = time.time() - t_start
    print(f"[{domain}] COMPLETED {len(docs_to_insert)} dates in {t_elapsed:.1f}s")
    return True, domain, len(docs_to_insert)

# =========================================================
# MAIN
# =========================================================

def main():
    dates = generate_date_range(START_DATE, END_DATE)
    docs = list(input_col.find({}))

    print("=" * 60)
    print("DAILYSTATS OLD - HISTORICAL DATA PROCESSING")
    print(f"Date range   : {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')} ({len(dates)} days)")
    print(f"Total domains: {len(docs)}")
    print(f"Target col   : daily_stats.oldstats")
    print(f"Parallelism  : {MAX_WORKERS} concurrent domains")
    print("=" * 60)

    # Clear oldstats as requested ("clear all the stats and run again")
    print("\nClearing oldstats collection...")
    deleted_result = oldstats_col.delete_many({})
    print(f"Cleared {deleted_result.deleted_count} existing records from daily_stats.oldstats.")

    # Ensure compound index
    oldstats_col.create_index([("Domain", 1), ("Date", 1)], background=True)

    success = 0
    failed = 0
    total_records = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_domain, d, dates): d.get("Domain") for d in docs}
        for future in as_completed(futures):
            dom = futures[future]
            try:
                ok, dom_name, count = future.result()
                if ok:
                    success += 1
                    total_records += count
                else:
                    failed += 1
            except Exception:
                failed += 1
                print(f"Unhandled error on domain {dom}: {traceback.format_exc()}")

    print("\n" + "=" * 60)
    print("HISTORICAL PROCESSING COMPLETE")
    print(f"Domains Succeeded: {success}/{len(docs)}")
    print(f"Domains Failed   : {failed}/{len(docs)}")
    print(f"Total records in oldstats: {oldstats_col.count_documents({})}")
    print("=" * 60)

    for client in CLIENT_CACHE.values():
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
