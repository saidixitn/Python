"""
EarnHaus export service
=======================

API request (counts) -> run Mongo queries -> write into the "EarnHaus" Google Sheet.

There are NO default counts. Whatever you send in the request body is what runs;
anything you leave out is skipped entirely (its tab is not touched).

    POST /export
    {
        "postings": 100,
        "updates": 100,
        "expires": 200,
        "datePosted": 5000
    }

Export types
------------
    postings    <- data_cleansing.ETL_AUD_Data        aggregate -> clientJobId
    updates     <- prod_jobiak_ai.job                 jobId, rolling validThrough cutoff
    expires     <- domain_expires.earnhaus_expires    jobId NOT IN updates ids
                   (collection is REBUILT first: active jobs - viewed jobs - semrush whitelist)
    datePosted  <- prod_jobiak_ai.job                 jobId, rolling validThrough cutoff

Order matters: updates runs first because expires excludes the update ids.

Run
---
    uvicorn earnhaus_export_api:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 600
    # one-shot / cron:
    python earnhaus_export_api.py --updates 100 --expires 200 --date-posted 5000

Requirements
------------
    pip install fastapi uvicorn pymongo gspread google-auth python-dotenv python-dateutil pydantic
"""

import os
import sys
import time
import argparse
import threading
import concurrent.futures
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import dateutil.parser
import gspread
import pymongo
from google.oauth2.service_account import Credentials
from pymongo import MongoClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv

load_dotenv()

# ================================================
# CONFIG
# ================================================
REMOTE_MONGO_URI = os.getenv("MONGO_URI")
CREDS_DB = "mongo_creds"

GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "EarnHaus")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",  # only needed to open by name
]

COMPANY = "Earn Haus"
EMPLOYER_ID = "68b8133b060e8f5df1a6c3a7"

# ---- Postings (data_cleansing.ETL_AUD_Data) ----
POSTINGS_DB = "data_cleansing"
POSTINGS_COLLECTION = "ETL_AUD_Data"
POSTINGS_TYPE = 1
POSTINGS_SAMPLE_SIZE = 50000
POSTINGS_IDS_PER_TITLE = 50
POSTINGS_TITLE_SAMPLE = 15
POSTINGS_TITLES = [
    "Feedback Associate (Up to $25/Task)",
    "Digital Tester (Earn $25 Per Review)",
    "Insight Provider (Immediate Start)",
    "Remote Front Desk Clerk",
    "Grocery Shopping Survey",
    "Market Researcher (100% Remote)",
    "Product Support",
    "Automotive Survey",
]

# ---- Updates / DatePosted (prod_jobiak_ai.job) ----
JOB_DOMAIN_KEY = "prod_jobiak_ai"
JOB_DB = "prod_jobiak_ai"
JOB_COLLECTION = "job"
EXCLUDED_TITLES = [
    "Online Survey Taker",
    "Online Survey Taker - Earn up to $1K every month",
    "Survey Taker",
]

# ---- Expires (built into domain_expires.earnhaus_expires on MONGO_URI) ----
EXPIRES_DB = "domain_expires"
EXPIRES_COLLECTION = "earnhaus_expires"
EXPIRES_DAYS = 30                 # view lookback window
EXPIRES_CHUNK_SIZE = 10_000
EXPIRES_MAX_WORKERS = 3

SEMRUSH_MONGO_URI = os.getenv("SEMRUSH_MONGO_URI")
SEMRUSH_DB_NAME = os.getenv("SEMRUSH_DB_NAME", "domain_expires")
SEMRUSH_COLLECTION = os.getenv("SEMRUSH_COLLECTION", "semrush_url's")
SEMRUSH_MATCH_DOMAIN = os.getenv("SEMRUSH_MATCH_DOMAIN", "earnhaus.com")

# ---- Logging ----
PROXY_DOMAIN_KEY = "proxy_stats"
PROXY_DB = "proxy_stats"
LOG_COLLECTION = "run_logs"

EXPORT_TYPES = ("postings", "updates", "expires", "datePosted")

_DB_CLIENTS: Dict[str, MongoClient] = {}
_LOCAL_CLIENT: Optional[MongoClient] = None
_GS_CLIENT = None
_RUN_LOCK = threading.Lock()


# ================================================
# MONGO
# ================================================
def local_client() -> MongoClient:
    """Client for the main cluster (mongo_creds + domain_expires live here)."""
    global _LOCAL_CLIENT
    if _LOCAL_CLIENT is None:
        if not REMOTE_MONGO_URI:
            raise RuntimeError("MONGO_URI environment variable is not set in .env")
        _LOCAL_CLIENT = MongoClient(REMOTE_MONGO_URI)
    return _LOCAL_CLIENT


def get_mongo_uri(domain_name: str) -> str:
    doc = local_client()[CREDS_DB]["creds"].find_one(
        {"domain": domain_name}, {"_id": 0, "mongo_uri": 1}
    )
    if doc and doc.get("mongo_uri"):
        print(f"[OK] Loaded mongo_uri for {domain_name}")
        return doc["mongo_uri"]
    raise RuntimeError(f"No mongo_uri found in {CREDS_DB}.creds for domain: {domain_name}")


def get_client(domain: str) -> MongoClient:
    if domain not in _DB_CLIENTS:
        _DB_CLIENTS[domain] = MongoClient(get_mongo_uri(domain))
    return _DB_CLIENTS[domain]


def get_collection(domain: str, db_name: str, collection: str):
    return get_client(domain)[db_name][collection]


def expires_db():
    """domain_expires lives on the main cluster."""
    return local_client()[EXPIRES_DB]


def log_run(doc: dict) -> None:
    try:
        col = get_collection(PROXY_DOMAIN_KEY, PROXY_DB, LOG_COLLECTION)
        doc["createdAt"] = datetime.now(timezone.utc)
        col.insert_one(doc)
    except Exception as e:  # logging must never break the export process
        print("[WARN] Could not write run log:", e)


# ================================================
# GOOGLE SHEETS
# ================================================
def get_sheets_client():
    global _GS_CLIENT
    if _GS_CLIENT is None:
        if not os.path.exists(GOOGLE_CREDS_FILE):
            raise RuntimeError(f"Service account file not found: {GOOGLE_CREDS_FILE}")
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=GOOGLE_SCOPES)
        _GS_CLIENT = gspread.authorize(creds)
    return _GS_CLIENT


def open_spreadsheet(name: Optional[str] = None):
    gc = get_sheets_client()
    if SPREADSHEET_ID:
        return gc.open_by_key(SPREADSHEET_ID)
    try:
        return gc.open(name or SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        raise RuntimeError(
            f"Spreadsheet '{name or SPREADSHEET_NAME}' not found. Share it with the "
            "client_email from credentials.json (Editor access)."
        )


def write_tab(sh, tab: str, header: List[str], rows: List[List], mode: str = "replace") -> int:
    n_cols = max(len(header), 1)
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=max(len(rows) + 10, 100), cols=n_cols)

    if mode == "append":
        if rows:
            ws.append_rows(rows, value_input_option="RAW")
        return len(rows)

    values = [header] + rows
    ws.clear()
    ws.resize(rows=max(len(values), 2), cols=n_cols)
    try:
        ws.update(range_name="A1", values=values, value_input_option="RAW")
    except TypeError:
        # Fallback for gspread < 6.0 signature
        ws.update("A1", values)
    try:
        ws.freeze(rows=1)
    except Exception:
        pass
    return len(rows)


def write_summary(sh, summary_rows: List[List]) -> None:
    header = ["RunAt (UTC)", "Company", "EmployerId", "Type", "Requested", "Exported", "Note"]
    try:
        ws = sh.worksheet("RunLog")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="RunLog", rows=500, cols=len(header))
        try:
            ws.update(range_name="A1", values=[header], value_input_option="RAW")
        except TypeError:
            ws.update("A1", [header])
    if summary_rows:
        ws.append_rows(summary_rows, value_input_option="RAW")


# ================================================
# POSTINGS (data_cleansing.ETL_AUD_Data)
# ================================================
def fetch_postings(employer_id: str, limit: int, titles: List[str]) -> List[Tuple[str, str]]:
    """Returns [(title, clientJobId), ...] spread evenly across the sampled titles."""
    col = get_collection(POSTINGS_DB, POSTINGS_DB, POSTINGS_COLLECTION)

    pipeline = [
        {"$match": {
            "employerId": employer_id,
            "Type": POSTINGS_TYPE,
            "title": {"$in": titles},
        }},
        {"$sample": {"size": POSTINGS_SAMPLE_SIZE}},
        {"$group": {"_id": "$title", "ids": {"$push": "$clientJobId"}}},
        {"$project": {
            "_id": 0,
            "title": "$_id",
            "ids": {"$slice": ["$ids", POSTINGS_IDS_PER_TITLE]},
        }},
        {"$sample": {"size": POSTINGS_TITLE_SAMPLE}},
    ]

    groups = list(col.aggregate(pipeline, allowDiskUse=False))
    print(f"[INFO] Postings: {len(groups)} title groups returned")

    out: List[Tuple[str, str]] = []
    seen = set()
    idx = 0
    while len(out) < limit:
        added = False
        for g in groups:
            ids = g.get("ids") or []
            if idx < len(ids):
                jid = ids[idx]
                if jid and jid not in seen:
                    seen.add(jid)
                    out.append((g.get("title", ""), jid))
                    added = True
                if len(out) >= limit:
                    break
        if not added:
            break
        idx += 1

    print(f"[INFO] Postings: {len(out)} ids selected (requested {limit})")
    return out[:limit]


# ================================================
# UPDATES + DATEPOSTED (prod_jobiak_ai.job)
# ================================================
def pick_cutoff(results: List[dict], needed: int) -> Optional[str]:
    """Walk validThrough dates oldest-first until `needed` jobs are covered."""
    total = 0
    for r in results:
        total += r["count"]
        if total >= needed:
            return r["date"]
    return results[-1]["date"] if results else None


def fetch_job_pool(employer_id: str, needed: int) -> Tuple[List[str], Optional[str], List[dict]]:
    col = get_collection(JOB_DOMAIN_KEY, JOB_DB, JOB_COLLECTION)

    base_match = {
        "employerId": employer_id,
        "status": "posted",
        "isActive": True,
        "datePosted": {"$exists": True},
        "title": {"$nin": EXCLUDED_TITLES},
    }

    pipeline = [
        {"$match": base_match},
        {"$addFields": {"date": {
            "$dateToString": {"format": "%Y-%m-%d", "date": "$validThrough"}
        }}},
        {"$group": {"_id": {"date": "$date"}, "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "date": "$_id.date", "count": 1}},
        {"$sort": {"date": 1}},
    ]

    summary = list(col.aggregate(pipeline))
    cutoff = pick_cutoff(summary, needed)
    if not cutoff:
        print("[WARN] No jobs matched for updates/datePosted")
        return [], None, summary

    end_window = dateutil.parser.parse(cutoff + "T00:00:00Z") + timedelta(days=1)

    query = dict(base_match)
    query["validThrough"] = {"$lt": end_window}

    cursor = col.find(query, {"_id": 0, "jobId": 1}).sort("validThrough", 1).limit(needed)
    job_ids = [d["jobId"] for d in cursor if d.get("jobId")]

    print(f"[INFO] Job pool: {len(job_ids)} ids (cutoff {cutoff}, needed {needed})")
    return job_ids, cutoff, summary


# ================================================
# EXPIRES : BUILD (active jobs - viewed jobs - semrush whitelist)
# ================================================
def _fetch_active_jobs(prod_db, employer_id: str) -> Dict[str, dict]:
    print("  [Worker: Jobs] Querying prod_jobiak_ai.job ...")
    query = {
        "employerId": employer_id,
        "status": "posted",
        "datePosted": {"$exists": True},
    }
    projection = {
        "_id": 0,
        "jobId": 1,
        "validThrough": 1,
        "submittedUrl": 1,
        "jobtitle": 1,
        "company": 1,
    }

    jobs = {}
    cursor = prod_db["job"].find(query, projection)
    for doc in cursor:
        jid = doc.get("jobId")
        if jid:
            jobs[jid] = doc
    cursor.close()

    print(f"  [Worker: Jobs] Finished. Found {len(jobs):,} jobs.")
    return jobs


def _fetch_viewed_ids(prod_db, employer_id: str, start_date, end_date) -> set:
    print("  [Worker: Views] Querying prod_jobiak_ai.userAnalytics ...")
    query = {
        "employerId": employer_id,
        "isBot": False,
        "browserType": {"$ne": "Unknown"},
        "deviceType": {"$ne": "Unknown"},
        "isFromGoogle": True,
        "createdDt": {"$gt": start_date, "$lt": end_date},
    }

    viewed = set()
    cursor = prod_db["userAnalytics"].find(query, {"jobId": 1})
    for doc in cursor:
        jid = doc.get("jobId")
        if jid:
            viewed.add(jid)
    cursor.close()

    print(f"  [Worker: Views] Finished. {len(viewed):,} distinct viewed jobs.")
    return viewed


def _fetch_semrush_urls() -> set:
    if not SEMRUSH_MONGO_URI:
        raise RuntimeError(
            "SEMRUSH_MONGO_URI is not set. Add it to .env, or call /export with "
            '"rebuildExpires": false to reuse the existing earnhaus_expires collection.'
        )

    print(f"  [Worker: Semrush] Querying whitelist for {SEMRUSH_MATCH_DOMAIN} ...")
    client = pymongo.MongoClient(SEMRUSH_MONGO_URI)
    try:
        query = {"view_exists": {"$exists": False}, "domain": SEMRUSH_MATCH_DOMAIN}
        cursor = client[SEMRUSH_DB_NAME][SEMRUSH_COLLECTION].find(query, {"url": 1})
        urls = {d["url"] for d in cursor if d.get("url")}
    finally:
        client.close()

    print(f"  [Worker: Semrush] Finished. {len(urls):,} whitelist URLs.")
    return urls


def build_expires(
    employer_id: str,
    collection_name: str = EXPIRES_COLLECTION,
    days: int = EXPIRES_DAYS,
) -> dict:

    print("\n========== BUILDING EXPIRES COLLECTION ==========")
    t0 = time.time()

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    end_date = now

    prod_db = get_client(JOB_DOMAIN_KEY)[JOB_DB]
    exp_db = expires_db()

    with concurrent.futures.ThreadPoolExecutor(max_workers=EXPIRES_MAX_WORKERS) as ex:
        f_jobs = ex.submit(_fetch_active_jobs, prod_db, employer_id)
        f_views = ex.submit(_fetch_viewed_ids, prod_db, employer_id, start_date, end_date)
        f_semrush = ex.submit(_fetch_semrush_urls)

        jobs_dict = f_jobs.result()
        viewed_ids = f_views.result()
        semrush_urls = f_semrush.result()

    all_job_ids = set(jobs_dict.keys())
    no_view_ids = all_job_ids - viewed_ids

    docs = []
    semrush_skipped = 0
    for jid in no_view_ids:
        job_doc = jobs_dict[jid]
        url = job_doc.get("submittedUrl")
        if url and url in semrush_urls:
            semrush_skipped += 1
            continue
        docs.append(job_doc)

    print(f"  - Total active jobs : {len(all_job_ids):,}")
    print(f"  - Jobs with views   : {len(viewed_ids):,}")
    print(f"  - Semrush protected : {semrush_skipped:,}")
    print(f"  = Expiry candidates : {len(docs):,}")

    if docs:
        if collection_name in exp_db.list_collection_names():
            exp_db.drop_collection(collection_name)
        col = exp_db[collection_name]
        for i in range(0, len(docs), EXPIRES_CHUNK_SIZE):
            col.insert_many(docs[i:i + EXPIRES_CHUNK_SIZE])
        print(f"[OK] Wrote {len(docs):,} docs to {EXPIRES_DB}.{collection_name}")
    else:
        print("[WARN] No expiry candidates - existing collection left untouched.")

    stats = {
        "totalActiveJobs": len(all_job_ids),
        "jobsWithViews": len(viewed_ids),
        "semrushProtected": semrush_skipped,
        "candidates": len(docs),
        "lookbackDays": days,
        "collection": collection_name,
        "buildSeconds": round(time.time() - t0, 2),
    }
    print(f"========== BUILD DONE in {stats['buildSeconds']}s ==========\n")
    return stats


# ================================================
# EXPIRES : FETCH IDS
# ================================================
def fetch_expires(limit: int, exclude_ids: List[str], collection_name: str) -> List[str]:
    col = expires_db()[collection_name]

    query = {"jobId": {"$nin": exclude_ids}} if exclude_ids else {}
    cursor = col.find(query, {"_id": 0, "jobId": 1}).limit(limit)
    ids = [d["jobId"] for d in cursor if d.get("jobId")]

    print(f"[INFO] Expires: {len(ids)} ids (requested {limit}, excluded {len(exclude_ids)})")
    return ids


# ================================================
# MAIN EXPORT ROUTINE
# ================================================
def run_export(
    counts: Dict[str, int],
    employer_id: str = EMPLOYER_ID,
    company: str = COMPANY,
    spreadsheet: Optional[str] = None,
    expires_collection: str = EXPIRES_COLLECTION,
    expires_days: int = EXPIRES_DAYS,
    rebuild_expires: bool = True,
    mode: str = "replace",
    date_posted_excludes_updates: bool = False,
    dry_run: bool = False,
) -> dict:

    today = datetime.today().strftime("%Y-%m-%d")
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    t0 = time.time()

    print(f"\n[INFO] Export {company} ({employer_id}) -> {counts}")

    result = {
        "company": company,
        "employerId": employer_id,
        "date": today,
        "requested": counts,
        "exported": {},
        "cutoff": None,
        "expiresBuild": None,
        "spreadsheet": spreadsheet or SPREADSHEET_NAME,
        "dryRun": dry_run,
    }

    update_ids: List[str] = []
    date_posted_ids: List[str] = []
    expire_ids: List[str] = []
    postings: List[Tuple[str, str]] = []
    day_summary: List[dict] = []

    wants_updates = "updates" in counts
    wants_date_posted = "datePosted" in counts

    # ---- 1. updates + datePosted share one job pool ----
    if wants_updates or wants_date_posted:
        n_updates = counts.get("updates", 0)
        n_date_posted = counts.get("datePosted", 0)

        if date_posted_excludes_updates:
            pool_needed = n_updates + n_date_posted
        else:
            pool_needed = max(n_updates, n_date_posted)

        job_pool, cutoff, day_summary = fetch_job_pool(employer_id, pool_needed)
        result["cutoff"] = cutoff

        if wants_updates:
            update_ids = job_pool[:n_updates]
        if wants_date_posted:
            if date_posted_excludes_updates:
                date_posted_ids = job_pool[n_updates:n_updates + n_date_posted]
            else:
                date_posted_ids = job_pool[:n_date_posted]

    # ---- 2. expires: rebuild the collection, then pull ids ----
    if "expires" in counts:
        if rebuild_expires:
            result["expiresBuild"] = build_expires(employer_id, expires_collection, expires_days)
        else:
            print("[INFO] rebuildExpires=false - reusing existing collection")
        expire_ids = fetch_expires(counts["expires"], update_ids, expires_collection)

    # ---- 3. postings ----
    if "postings" in counts:
        postings = fetch_postings(employer_id, counts["postings"], POSTINGS_TITLES)

    if "postings" in counts:
        result["exported"]["postings"] = len(postings)
    if wants_updates:
        result["exported"]["updates"] = len(update_ids)
    if "expires" in counts:
        result["exported"]["expires"] = len(expire_ids)
    if wants_date_posted:
        result["exported"]["datePosted"] = len(date_posted_ids)

    if dry_run:
        print("[INFO] Dry run - nothing written to Google Sheets")
        result["sampleIds"] = {
            "postings": [p[1] for p in postings[:5]],
            "updates": update_ids[:5],
            "expires": expire_ids[:5],
            "datePosted": date_posted_ids[:5],
        }
        result["elapsedSeconds"] = round(time.time() - t0, 2)
        return result

    # ---- 4. write to Google Sheets ----
    sh = open_spreadsheet(spreadsheet)

    if "postings" in counts:
        write_tab(sh, "Postings", ["title", "clientJobId"], [[t, i] for t, i in postings], mode)
    if wants_updates:
        write_tab(sh, "Updates", ["jobId"], [[i] for i in update_ids], mode)
    if "expires" in counts:
        write_tab(sh, "Expires", ["jobId"], [[i] for i in expire_ids], mode)
    if wants_date_posted:
        write_tab(sh, "DatePosted", ["jobId"], [[i] for i in date_posted_ids], mode)

    notes = {
        "updates": f"cutoff={result['cutoff']}",
        "datePosted": f"cutoff={result['cutoff']}",
        "expires": (
            f"candidates={result['expiresBuild']['candidates']}"
            if result["expiresBuild"] else "reused existing collection"
        ),
        "postings": "",
    }
    write_summary(sh, [
        [run_at, company, employer_id, key, counts[key], result["exported"][key], notes.get(key, "")]
        for key in EXPORT_TYPES if key in counts
    ])

    result["spreadsheetUrl"] = sh.url
    result["elapsedSeconds"] = round(time.time() - t0, 2)
    print("[OK] Sheet updated:", sh.url)

    log_run({
        "EmployerId": employer_id,
        "Company": company,
        "date": today,
        "type": "sheet_export",
        "requested": counts,
        "exported": result["exported"],
        "cutoff": result["cutoff"],
        "expiresBuild": result["expiresBuild"],
        "validThroughSummary": day_summary,
        "spreadsheet": result["spreadsheet"],
        "exportDone": True,
    })

    return result


# ================================================
# API
# ================================================
app = FastAPI(title="EarnHaus Export API", version="2.0")


class ExportRequest(BaseModel):
    employerId: str = Field(default=EMPLOYER_ID)
    company: str = Field(default=COMPANY)

    postings: Optional[int] = Field(default=None, ge=0)
    updates: Optional[int] = Field(default=None, ge=0)
    expires: Optional[int] = Field(default=None, ge=0)
    datePosted: Optional[int] = Field(default=None, ge=0)

    spreadsheet: Optional[str] = None
    expiresCollection: str = EXPIRES_COLLECTION
    expiresDays: int = Field(default=EXPIRES_DAYS, ge=1)
    rebuildExpires: bool = True
    mode: str = Field(default="replace", pattern=r"^(replace|append)$")
    datePostedExcludesUpdates: bool = False
    dryRun: bool = False

    @model_validator(mode="after")
    def at_least_one(self):
        if all(getattr(self, k) is None for k in EXPORT_TYPES):
            raise ValueError(
                "Send at least one count: postings, updates, expires or datePosted"
            )
        return self

    def counts(self) -> Dict[str, int]:
        return {k: getattr(self, k) for k in EXPORT_TYPES if getattr(self, k) is not None}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "spreadsheet": SPREADSHEET_NAME,
        "time": datetime.now(timezone.utc),
    }


@app.post("/export")
def export(req: ExportRequest):
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An export is already running")

    try:
        return run_export(
            counts=req.counts(),
            employer_id=req.employerId,
            company=req.company,
            spreadsheet=req.spreadsheet,
            expires_collection=req.expiresCollection,
            expires_days=req.expiresDays,
            rebuild_expires=req.rebuildExpires,
            mode=req.mode,
            date_posted_excludes_updates=req.datePostedExcludesUpdates,
            dry_run=req.dryRun,
        )
    except HTTPException:
        raise
    except Exception as e:
        log_run({
            "EmployerId": req.employerId,
            "Company": req.company,
            "date": datetime.today().strftime("%Y-%m-%d"),
            "type": "sheet_export",
            "requested": req.counts(),
            "exportDone": False,
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _RUN_LOCK.release()


@app.post("/expires/build")
def expires_build(
    employerId: str = EMPLOYER_ID,
    collection: str = EXPIRES_COLLECTION,
    days: int = EXPIRES_DAYS,
):
    """Rebuild the expires collection only, without touching the sheet."""
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An export is already running")
    try:
        return build_expires(employerId, collection, days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _RUN_LOCK.release()


# ================================================
# CLI (cron friendly)
# ================================================
def _cli():
    p = argparse.ArgumentParser(description="EarnHaus export -> Google Sheet")
    p.add_argument("--employer-id", default=EMPLOYER_ID)
    p.add_argument("--company", default=COMPANY)
    p.add_argument("--postings", type=int)
    p.add_argument("--updates", type=int)
    p.add_argument("--expires", type=int)
    p.add_argument("--date-posted", type=int)
    p.add_argument("--spreadsheet")
    p.add_argument("--expires-collection", default=EXPIRES_COLLECTION)
    p.add_argument("--expires-days", type=int, default=EXPIRES_DAYS)
    p.add_argument("--no-rebuild-expires", action="store_true")
    p.add_argument("--mode", choices=["replace", "append"], default="replace")
    p.add_argument("--date-posted-excludes-updates", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    counts = {}
    for key, val in (
        ("postings", args.postings),
        ("updates", args.updates),
        ("expires", args.expires),
        ("datePosted", args.date_posted),
    ):
        if val is not None:
            counts[key] = val

    if not counts:
        sys.exit("Pass at least one of --postings --updates --expires --date-posted")

    out = run_export(
        counts=counts,
        employer_id=args.employer_id,
        company=args.company,
        spreadsheet=args.spreadsheet,
        expires_collection=args.expires_collection,
        expires_days=args.expires_days,
        rebuild_expires=not args.no_rebuild_expires,
        mode=args.mode,
        date_posted_excludes_updates=args.date_posted_excludes_updates,
        dry_run=args.dry_run,
    )
    print(out)


if __name__ == "__main__":
    _cli()