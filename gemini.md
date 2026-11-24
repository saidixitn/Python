# GEMINI MASTER KNOWLEDGE BASE & ENGINEERING ENCYCLOPEDIA
**Complete LLM-Grade Technical Reference for Jobiak Search Engineering, Multi-Tenant MongoDB Infrastructure, Production Queries, Live Schemas, Indexes, Input/Output Contracts, Python/VPS Pipelines & Operations Dictionary**

---

## How to Use This Knowledge Base (For Humans & AI Agents)

This file is the **single, authoritative, encyclopedic technical specification** for every database, collection, index, query, formula, API, cron daemon, and reporting pipeline across all 6 Jobiak engineering repositories (`Python`, `pm2-vps`, `vps-automations`, `Job-Posting-Alerts`, `Automation`, `PythonProject`).

For every subsystem, this manual answers:
1. **WHAT** it is and **WHY** it exists (the business problem & SEO/Google for Jobs requirement).
2. **WHEN** and **HOW** to run it (CLI commands, PM2 schedules, GitHub Actions crons, API endpoints).
3. **INPUT & OUTPUT** contracts (exact source/target DBs, collections, Google Sheets, and **real JSON document examples**).
4. **INDEXES & PERFORMANCE RULES** (exact MongoDB index keys and `hint(...)` calls so queries finish in seconds instead of timing out).
5. **READY-TO-RUN QUERIES** (both **PyMongo** and **Mongo Shell / Studio 3T** copy-paste queries).
6. **MASTER FIELD & TERMINOLOGY DICTIONARY** (every field, status code, flag, and edge case defined cleanly).

> [!IMPORTANT]
> **Rules When Generating Any New Code:**
> 1. Always place newly generated scripts, CSVs, and Excel workbooks inside `antigravity/` so the repository root stays clean.
> 2. Never run inline `python -c "... '$match' ..."` in Windows PowerShell — PowerShell treats `$match`, `$group`, `$ne` as empty shell variables! Always write standalone `.py` scripts inside `antigravity/`.
> 3. Never hardcode plaintext `.env` passwords into tracked Git files. Always load via `python-dotenv` (`load_dotenv()`) + `mongo_creds.creds`.

---

## Table of Contents

1. [Server Infrastructure & Multi-Tenant MongoDB Connection Guide](#1-server-infrastructure--multi-tenant-mongodb-connection-guide)
2. [Universal Copy-Paste Easy-Connect Library (`db_helper`)](#2-universal-copy-paste-easy-connect-library-db_helper)
3. [The 3 Platform Architectures (Proxy, Direct Apply, Programmatic)](#3-the-3-platform-architectures-proxy-direct-apply-programmatic)
4. [Production Collections, Real Sample Docs & MongoDB Indexes Atlas](#4-production-collections-real-sample-docs--mongodb-indexes-atlas)
5. [Google Views/Clicks & Bot Traffic Filtering Logic (Exact Queries)](#5-google-viewsclicks--bot-traffic-filtering-logic-exact-queries)
6. [Daily Stats Pipeline (`Stats/dailystats.py` & `dailystats_old.py`) — Complete Deep Dive](#6-daily-stats-pipeline-statsdailystatspy--dailystats_oldpy--complete-deep-dive)
7. [Enterprise Clicks Report Dashboard & API (`pm2-vps/Clicks Report/clicks_report.py`)](#7-enterprise-clicks-report-dashboard--api-pm2-vpsclicks-reportclicks_reportpy)
8. [Proxy Export & TargetP4 Audit Microservice (`pm2-vps/Proxy/` & `Proxy/`)](#8-proxy-export--targetp4-audit-microservice-pm2-vpsproxy--proxy)
9. [Expiring-Soon Alerts & Sliding-Window Updates (`updates.py` & `pub_expired_check.py`)](#9-expiring-soon-alerts--sliding-window-updates-updatespy--pub_expired_checkpy)
10. [Zero-Click Expiration, Feed Reconciliation (`expires.py`), Updates (`updates.py`) & `jobicarenode_prod` Ingestion Collision Check](#10-zero-click-expiration-feed-reconciliation-expirespy-updatespy--jobicarenode_prod-ingestion-collision-check)
11. [Duplicate Detection (`concentrix_expires.py`), Feed vs Expanded (`feed.py`) & Keyword Postings (`postings.py`)](#11-duplicate-detection-concentrix_expirespy-feed-vs-expanded-feedpy--keyword-postings-postingspy)
12. [Root Workspace Client Analytics: HCSG, Lettuce, ABS Kids, QRM, YES Communities, Day-1 Reports & XML Comparison](#12-root-workspace-client-analytics-hcsg-lettuce-abs-kids-qrm-yes-communities-day-1-reports--xml-comparison)
13. [Real-Time Telegram Alerts & XML Feed Mutex Lock (`Job-Posting-Alerts`)](#13-real-time-telegram-alerts--xml-feed-mutex-lock-job-posting-alerts)
14. [BigQuery Streaming, Search Console & NDJSON Bulk Exports](#14-bigquery-streaming-search-console--ndjson-bulk-exports)
15. [Revenue & Affiliate Reconciliation (`banana.py`, `whatjobs.py`, `jobget.py`, `earnhaus_prog.py`)](#15-revenue--affiliate-reconciliation-bananapy-whatjobspy-jobgetpy-earnhaus_progpy)
16. [GenAI FAQ Engine, Keywords Schemas, ATS Description Quality & Scrape Cleaners](#16-genai-faq-engine-keywords-schemas-ats-description-quality--scrape-cleaners)
17. [Production VPS PM2 Ecosystem & Automated Cloud Backups](#17-production-vps-pm2-ecosystem--automated-cloud-backups)
18. [Master Engineering Dictionary (A–Z)](#18-master-engineering-dictionary-a-z)
19. [How to Ask & Standard Execution Playbook](#19-how-to-ask--standard-execution-playbook)

---

## 1. Server Infrastructure & Multi-Tenant MongoDB Connection Guide

### Why Multi-Tenant Routing Exists
Jobiak runs over **1,200 MongoDB databases** distributed across dedicated production servers (AWS/GCP/VPS nodes). Hardcoding connection strings in individual analytics scripts is impossible to maintain when credentials rotate or new domains spin up.

Instead, the infrastructure uses a **Hub-and-Spoke Discovery Architecture**:
1. **The Central VPS Hub (`<CENTRAL_VPS_IP>:27017`)** stores the master cluster URIs inside **`mongo_creds.uri`** and Google Service Account JSON inside **`google_creds.creds`**.
2. **PM2 Process `mongo-creds-sync` (`new_creds.py`)** runs daily at **`00:30 UTC`**, connects to every cluster URI in `mongo_creds.uri`, runs `list_database_names()`, measures ping latency, and upserts one routing record per database into **`mongo_creds.creds`**.
3. **Every Python script** only needs **`MONGO_URI`** from `.env` (which points to `<CENTRAL_VPS_IP>:27017`), looks up `{"domain": "<target_db>"}` inside `mongo_creds.creds`, URL-encodes any special characters in the password (`$`, `^`, `*`, `!`), and opens a cached `MongoClient`.

### Complete Server IP & Database Topology Map

| Server IP / Host | Role / Environment | Key Databases Hosted |
|---|---|---|
| **`<CENTRAL_VPS_IP>:27017`** | **Central VPS Hub** (`MONGO_URI`) | `mongo_creds`, `google_creds`, `daily_stats`, `daily_domain_stats`, `Clicks_Report`, `domain_expires`, `domain_postings`, `xml_timings`, `banana_analytics`, `GenAI`, `GSC`, `surveys_prod`, `XML`, `dc_prod`, `proxy_stats` |
| **`<PROXY_CLUSTER_IP>:27017`** | **Proxy Production Cluster** | `prod_jobiak_ai` *(all Proxy clients: HCSG, ABS Kids, Concentrix, QRM, YES!, Earn Haus, Champion Window, Imperial Supplies, US Jobs Placement, Suncrest Care)* |
| **`<DIRECT_APPLY_CLUSTER_IP>:27017`** | **Direct Apply Production Cluster** | `directclients_prod` *(all Direct Apply subdomains: `gfj.lettuce.com`, `gfj.apexfocusgroup.com`, `gfj.levelsurveys.com`, `jobs.uncommonschools.org`, etc.)* |
| **`<XML_FEED_CLUSTER_IP>:27017`** | **XML Feed & Scheduler Cluster** | `generateXml_prod` *(396+ `emp-gxc-*` feed collections)*, `PJP_Schedular`, `webharvester`, `canteen_jobiak`, `selectmedical_jobs` |
| **`<SCRAPING_CLUSTER_IP>:27017`** | **Scraping & Audit Cluster** | `ETL_Scrapping_Data` *(raw feeds)*, `data_cleansing` *(`ETL_AUD_Data`, `ETL_Job_Log` audit logs)* |
| **`<ALLJOBS_CLUSTER_IP>:27017`** | **AllJobs Production Cluster** | `alljobs_prod` |
| **`<PROGRAMMATIC_NODE_IP>:27017`** | **Programmatic Node / Scraping Cluster** | `jobicarenode_prod` *(`emp-jicn-*` Proxy staging/feed source)*, `PJP_Scrapping_Data`, `medichire`, `worksearchersonline_prod`, etc. |
| **`<BOT_TELEMETRY_IP>:27017`** | **Bot Telemetry & Detective Cluster** | `BOT_VISITS_DATA`, `analyst_db`, `google_detective` |
| **`<SHARD_IP_1>`, `<SHARD_IP_2>`, `<SHARD_IP_3>`, `<SHARD_IP_4>`, `<SHARD_IP_5>`, `<SHARD_IP_6>`, `<SHARD_IP_7>`, `<SHARD_IP_8>`, `<SHARD_IP_9>`** | **Programmatic Multi-Tenant Shards** | ~1,150+ individual `{client}_prod` databases *(e.g. `hextill_prod`, `justopinionjobs_prod`, `earnwithwfh_prod`, `vertexisle_prod`)* |

> [!WARNING]
> **Special Case (`v2valuejobs_prod`):** Keep in mind that `mongo_creds.creds` may point `v2valuejobs_prod` to an older IP (`<LEGACY_SHARD_IP>`) that can time out, whereas a local copy of `v2valuejobs_prod` (`alternative_desc_change`, `companies`, `static_keywords`, `userAnalytics`) also exists directly on `<CENTRAL_VPS_IP>`. Always inspect `mongo_creds.creds` latency/errors if a remote shard times out.

### `.env` Variables Reference (Root `./.env`)
```ini
# MongoDB Core Handles
MONGO_URI=...                      # Primary Central Hub (<CENTRAL_VPS_IP>:27017)
LOCAL_DOMAIN_MONGOS=false          # Set true in Revenue/banana.py to test against localhost
BANANA_MONGO_URI=mongodb://localhost:27017

# Google Cloud / Sheets / BigQuery
GOOGLE_CREDENTIALS=credentials.json
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
PROJECT_ID=your-project-id
JOBGET_GOOGLE_SHEET_ID=your_jobget_sheet_id_here
WHATJOBS_SPREADSHEET_ID=your_whatjobs_sheet_id_here

# SMTP (Gmail SSL Port 465)
SMTP_PASS=...                      # Gmail App Password
SMTP_USER=your-email@example.com
SMTP_SENDER=your-email@example.com
SMTP_RECEIVER=your-email@example.com
SMTP_CC=dev-team@example.com

# APIs & GenAI
IS_REMOTE_API_URL=http://<IS_REMOTE_API_HOST>:5111/update_is_remote
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
```

---

## 2. Universal Copy-Paste Easy-Connect Library (`db_helper`)

To make running any query or script effortless, copy this thread-safe connection module. It handles `.env` loading, URI special-character URL encoding (`quote_plus`), connection pooling (`maxPoolSize=100`), Central Hub fallbacks, domain-type resolution, and MongoDB-stored Google Credentials.

```python
import os
import threading
from urllib.parse import urlparse, urlunparse, quote_plus
from dotenv import load_dotenv
from pymongo import MongoClient
from google.oauth2.service_account import Credentials

load_dotenv(r"./.env")

CENTRAL_URI = os.getenv("MONGO_URI")
_CENTRAL_CLIENT = None
_CLIENT_CACHE = {}
_DB_CACHE = {}
_LOCK = threading.Lock()


def safe_encode_uri(uri: str) -> str:
    """URL-encodes MongoDB username/password containing $, ^, *, !, @ without breaking query params."""
    if not uri or not uri.startswith("mongodb"):
        return uri
    p = urlparse(uri)
    if p.username or p.password:
        auth = quote_plus(p.username or "")
        if p.password:
            auth += f":{quote_plus(p.password)}"
        netloc = f"{auth}@{p.hostname}" + (f":{p.port}" if p.port else "")
        return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
    return uri


def get_central_client() -> MongoClient:
    """Returns cached MongoClient for the Central VPS Hub (<CENTRAL_VPS_IP>)."""
    global _CENTRAL_CLIENT
    if _CENTRAL_CLIENT is None:
        if not CENTRAL_URI:
            raise RuntimeError("MONGO_URI missing in .env")
        _CENTRAL_CLIENT = MongoClient(
            safe_encode_uri(CENTRAL_URI),
            maxPoolSize=100,
            serverSelectionTimeoutMS=8000,
            socketTimeoutMS=60000,
        )
    return _CENTRAL_CLIENT


def connect_db(db_name: str):
    """
    One-line connector for ANY Jobiak DB (Central or any of the 1,200+ remote DBs).
    Example:
        db = connect_db("prod_jobiak_ai")
        db = connect_db("directclients_prod")
        db = connect_db("hextill_prod")
        db = connect_db("ETL_Scrapping_Data")
        db = connect_db("daily_stats")
    """
    with _LOCK:
        if db_name in _DB_CACHE:
            return _DB_CACHE[db_name]

    central = get_central_client()
    cred = central["mongo_creds"]["creds"].find_one({"domain": db_name}, {"_id": 0, "mongo_uri": 1})

    if not cred or not cred.get("mongo_uri"):
        # Database resides directly on Central VPS Hub (e.g. daily_stats, Clicks_Report, GenAI)
        db = central[db_name]
    else:
        uri = safe_encode_uri(cred["mongo_uri"])
        with _LOCK:
            if uri not in _CLIENT_CACHE:
                _CLIENT_CACHE[uri] = MongoClient(
                    uri,
                    maxPoolSize=100,
                    serverSelectionTimeoutMS=10000,
                    socketTimeoutMS=60000,
                )
            db = _CLIENT_CACHE[uri][db_name]

    with _LOCK:
        _DB_CACHE[db_name] = db
    return db


def connect_by_domain_type(domain: str, domain_type: str):
    """Resolves Proxy -> prod_jobiak_ai, Direct Apply -> directclients_prod, Programmatic -> {slug}_prod."""
    dt = (domain_type or "").strip().lower()
    if dt == "proxy":
        return connect_db("prod_jobiak_ai")
    if dt in ("direct apply", "direct_apply", "direct-apply", "sub", "subdomain"):
        return connect_db("directclients_prod")
    slug = (
        domain.replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
        .split(".")[0]
        .lower()
        .strip()
    )
    return connect_db(f"{slug}_prod")


def get_google_creds(scopes=None):
    """Loads Google Service Account credentials directly from Central Hub google_creds.creds."""
    scopes = scopes or [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/bigquery",
    ]
    central = get_central_client()
    doc = central["google_creds"]["creds"].find_one({"name": "google_credentials"}) or central["google_creds"]["creds"].find_one({}, {"content": 1})
    return Credentials.from_service_account_info(doc["content"], scopes=scopes)
```

---

## 3. The 3 Platform Architectures (Proxy, Direct Apply, Programmatic)

Understanding **which database, collection, ID field, and employer filter** applies to a domain prevents 99% of wrong-number bugs:

| Dimension | 1. Proxy | 2. Direct Apply (Subdomain) | 3. Programmatic |
|---|---|---|---|
| **What It Means** | Client jobs hosted behind a reverse-proxied subdirectory (`/gfj/`, `/jobiak/`) on the client's root domain. | Client jobs hosted on a Jobiak-managed subdomain (`gfj.lettuce.com`, `jobs.uncommonschools.org`). | High-volume job aggregator websites wholly operated by Jobiak (`hextill.com`, `v2valuejobs.com`). |
| **MongoDB Database** | `prod_jobiak_ai` *(Shared across all Proxy clients)* | `directclients_prod` *(Shared across all Direct Apply clients)* | `{slug}_prod` *(Dedicated isolated DB per domain, e.g. `hextill_prod`)* |
| **Jobs Collection** | `job` | `Target_P4_Opt` | `Target_P4_Opt` |
| **Analytics Collection** | `userAnalytics` | `userAnalytics` *(+ historical `userAnalytics_old` / `userAnalytics_prod` in full-history reports)* | `userAnalytics` |
| **Google API Logs** | `jobsGoogleSubmittedLog` | `aj_jp_google_logs` | `aj_jp_google_logs` |
| **Employer Filter Required?** | **YES** — `{"employerId": {"$in": ids}}` *(CRITICAL: `prod_jobiak_ai` holds hundreds of employers!)* | **YES** — `{"employerId": {"$in": ids}}` *(CRITICAL: `directclients_prod` is shared!)* | **NO (`{}`)** for whole-domain stats; optional `employerId` if isolating one feed partner inside the domain. |
| **Job ID Field in Jobs Col** | `jobId` *(internal)*, `clientJobId` *(matches `jobicarenode_prod.Target_P4_Opt.uniqueKey`)* | `jobPubJobId` *(public ID)*, `uniqueKey` *(normalized title+loc+company hash)* | `jobPubJobId`, `uniqueKey` |
| **Job ID Field in `userAnalytics`** | `childJobId` *(used in bot/expiry/job-view joins)* & `jobId` *(used in Proxy `DB_Clicks` aggregation)* | `jobPubJobId` | `jobPubJobId` |
| **Title Field Name** | `title` | `jobtitle` | `jobtitle` |
| **Expiration Timestamp** | `validThrough` *(on `job`)* | `pub_expired` *(on `Target_P4_Opt`)* | `pub_expired` *(on `Target_P4_Opt`)* |
| **Active / Live Filter** | `{"status": "posted", "isActive": True}` | `{"gpost": 5, "job_status": {"$ne": 3}}` | `{"gpost": 5, "job_status": {"$ne": 3}}` |
| **Feed Expired Filter** | `data_cleansing.ETL_AUD_Data` with `Type: 0` | `{"job_status": 3}` | `{"job_status": 3}` |
| **Pending (`To_Post`) Filter** | `ETL_Scrapping_Data.ETL_Scraping_Data (job_status != 3)` minus `prod_jobiak_ai.job (status in [posted, removed])` | `{"gpost": 1, "job_status": {"$ne": 3}}` | `{"gpost": 1, "job_status": {"$ne": 3}}` |

### Active `daily_stats.input` Domain Roster (15 Monitored Domains)

| Domain | Type | `employerId` Filter Value |
|---|---|---|
| `hcsgcorp.com/gfj/` | Proxy | `"6a904f26060e8f0b78b0dc81"` |
| `abskids.com/gfj/` | Proxy | `"6aa8d214060e8f0b78b0dc87"` |
| `concentrix.com/gfj/` | Proxy | `"6a8871d1060e8f0b78b0dc69"` |
| `qrmhealth.com/gfj/` | Proxy | `"6a7b516d060e8f0b78b0dc5a"` |
| `yescommunities.com/gfj/` | Proxy | `"6a86c3d7060e8f0b78b0dc66"` |
| `championwindow.com/gfj` | Proxy | `"5f16b7fba780b2085c230ea1"` |
| `imperialsupplies.com/jobiak` | Proxy | `"5e6f1017a780b23e130a1c3b"` |
| `usjobsplacement.com/gfj/` | Proxy | `"6a62444b060e8f0b78b0dc1a"` |
| `earnhaus.com/gfj/` | Proxy | `"68b8133b060e8f5df1a6c3a7"` |
| `suncrestcare.com/gfj/` | Proxy | `"6ad8dd02060e8f0b78b0dc9a"` |
| `gfj.lettuce.com/` | Direct Apply | `"emp-jbk-lettuce"` |
| `gfj.apexfocusgroup.com` | Direct Apply | `["emp-jbk-apexfocusgroup", "emp-jbk-apexfocusgroup_uk"]` |
| `gfj.levelsurveys.com` | Direct Apply | `"emp-jbk-levelsurveys"` |
| `hextill.com` | Programmatic | `"emp-htc-clerkcrew1"` *(Programmatic ignores employerId in `dailystats.py`)* |
| `vertexisle.com` | Programmatic | `["emp-vxi-earnhaus", "emp-vxi-focusgrouppanel"]` |

---

## 4. Production Collections, Real Sample Docs & MongoDB Indexes Atlas

Every example below is taken **verbatim from live production MongoDB collections** so you know the exact field names, data types, and indexes available for fast queries.

---

### A. `prod_jobiak_ai.job` (Proxy Master Job Collection — 26 Indexes)
- **Example Document**:
```json
{
  "_id": "ObjectId(646790ed9d602a379ef7933c)",
  "jobId": "646790ec9d602a379ef7933a",
  "parentJobId": "646790ec9d602a379ef7933a",
  "clientJobId": "9399_1126_5176-7b24dd1b38662e5dfed79af8ea5b68bd",
  "employerId": "5f...",
  "domain": "https://gopuff.com",
  "url": "https://click.appcast.io/t/0in_E5z...",
  "submittedUrl": "https://gopuff.com/gfj/1-deliver-with-gopuff-hoboken-nj-646790ec9d602a379ef7933a",
  "title": "Deliver with Gopuff",
  "company": "Gopuff",
  "location": "Hoboken,NJ,US",
  "datePosted": "ISODate(2026-11-11T10:34:58.397Z)",
  "validThrough": "ISODate(2026-12-09T10:34:58.397Z)",
  "employmentType": "PART_TIME",
  "status": "posted",
  "isActive": true,
  "createdAt": "ISODate(2023-05-19T15:07:05.534Z)",
  "jobType": "ATS"
}
```
- **Critical Compound Indexes**:
  - `employerId_1_isActive_1_status_1`
  - `isActive_1_status_1_employerId_1_jobId_1`
  - `employerId_1_clientJobId_1`
  - `employerId_1_title_1_status_1_isActive_1`
  - `employerId_1_createdAt_1`, `datePosted_-1`, `jobId_-1`, `submittedUrl_1`

---

### B. `directclients_prod.Target_P4_Opt` & `hextill_prod.Target_P4_Opt` (64 & 59 Indexes)
- **Example Document**:
```json
{
  "_id": "ObjectId(644147112fe99409181dbf0c)",
  "employerId": "emp-jbk-websterandwebster",
  "client_name": "websterandwebster",
  "company": "Webster & Webster Associates",
  "jobtitle": "Embedded Software Engineer - Remote Position",
  "cleansedTitle": "Software Engineer",
  "uniqueKey": "embedded`engineer`position`remote`software~~portland~~or~~us~~associates`webster`webster",
  "main_uniqueKey": "embedded`engineer`position`remote`software~~portland~~or~~us~~associates`webster`webster",
  "jobPubJobId": "644147422fe99409181dbf11",
  "audId": "ObjectId(6956147425a408a0b9452574)",
  "uncleanedLocation": "Portland,OR,US",
  "gpost": 5,
  "job_status": 2,
  "action": "post",
  "gpost_date": "ISODate(...)",
  "pub_expired": "ISODate(...)",
  "lastCheckDate": "ISODate(2025-11-12T09:49:47.666Z)",
  "sourceURL": "http://<FEED_HOST>:8141/sitemap/Webster__Webster_Associates_jobs.xml",
  "url": "https://jobportal2.websterandwebster.com/careers/...",
  "occupationalcategory": "\"15-1133.00\",\"Software Developers, Systems Software\" "
}
```
- **Most Important Compound Indexes (Always match filter prefix!)**:
  - **`pub_expired_1_gpost_1`** *(Mandatory `hint("pub_expired_1_gpost_1")` in `updates.py` & `pub_expired_check.py`!)*
  - `employerId_1_job_status_1_gpost_1_gpost_date_1_action_1` *(Fast posted/updated/repost stats)*
  - `employerId_1_job_status_1_gpost_1_gpost_expire_date_1` *(Fast expiration stats)*
  - `job_status_1_gpost_1_employerId_1` *(Fast `To_Post` and `Posting_Queue` counts)*
  - `employerId_1_uniqueKey_1_job_status_1`
  - `gpost_1_job_status_1_gpost_date_1_view_exists_1_jobPubStatus_1_latest_user_view_date_1` *(Zero-click & view-exists audit)*

---

### C. `userAnalytics` (`prod_jobiak_ai` [13 Indexes] & `directclients_prod` [40 Indexes])
- **Example Document**:
```json
{
  "_id": "ObjectId(6a2d8b94469203d28fbe010d)",
  "ipAddress": "192.0.2.10",
  "userAgent": "Mozilla/5.0 ... (compatible; Googlebot/2.1; ...)",
  "requestUrl": "https://jobs.uncommonschools.org/jobdetails/bergenfield-nj-apprentice-teacher-66c3a35e8564f7340abd9fac",
  "submittedUrl": "https://jobs.uncommonschools.org/jobdetails/bergenfield-nj-apprentice-teacher-66c3a35e8564f7340abd9fac",
  "jobPubJobId": "66c3a35e8564f7340abd9fac",
  "childJobId": "...",
  "jobId": "...",
  "clientJobId": "743999930851881",
  "employerId": "emp-jbk-uncommonschools",
  "client_name": "uncommonschools",
  "jobtitle": "Apprentice Teacher",
  "location": "Bergenfield,  NJ,  US",
  "company": "Uncommon Schools",
  "isBot": true,
  "isFromGoogle": false,
  "browserType": "Unknown",
  "deviceType": "Unknown",
  "country": "United States",
  "action": "update",
  "viewType": "direct",
  "createdDt": "ISODate(2026-06-13T16:54:01.487Z)",
  "viewDate": "ISODate(2026-06-13T16:54:01.487Z)",
  "extraInfo": {
    "url": "https://uncommonschools.org/careers/jobs/...",
    "original_title": "apprentice teacher",
    "originalLocation": "Newark,NJ,US",
    "miles": 19.31,
    "locExpand": 1
  }
}
```
- **Most Important Compound Indexes**:
  - Proxy (`prod_jobiak_ai`): `childJobId_1_jobId_1_ipAddress_1_browser_1_createdDt_1`, `employerId_1`, `createdDt_1`, `jobId_-1`
  - Direct/Prog (`directclients_prod`): `isBot_1_createdDt_1_deviceType_1_browserType_1_countryCode_1_isFromGoogle_1`, `jobPubJobId_1_isBot_1_ipAddress_1_action_1_userAgent_1_createdDt_1_gpost_date_1`, `viewType_1_employerId_1_viewDate_1`

---

### D. `jobsGoogleSubmittedLog` & `aj_jp_google_logs` (Google Indexing API Audit Logs)
- **Example Document**:
```json
{
  "_id": "ObjectId(644404dc8778b8943723df64)",
  "callType": "URL_UPDATED",
  "jobId": "644147422fe99409181dbf11",
  "submittedUrl": "https://gfj.websterandwebster.com/jobdetails/...-644147422fe99409181dbf11",
  "employerId": "emp-jbk-websterandwebster",
  "projectId": "cupcake-indexing1",
  "createdAt": "ISODate(2023-04-22T16:01:32.026Z)",
  "status_update": 2,
  "response": "success: {\n  \"urlNotificationMetadata\": { ... }\n}"
}
```
- **Indexes**: `createdAt_1_callType_1`, `createdAt_1_status_update_1_callType_1`, `jobId_1`, `employerId_1_submittedUrl_1`, `company_1_callType_1_createdAt_1`.

---

### E. `ETL_Scrapping_Data.ETL_Scraping_Data` & `data_cleansing.ETL_AUD_Data` (Proxy Feeds)
- **Note the spelling**: Database is **`ETL_Scrapping_Data`** (double `p`), Collection is **`ETL_Scraping_Data`** (single `p`).
- **`ETL_Scraping_Data` Sample Doc**: `{"clientJobId": "16653032", "employerId": "601d16fba780b2282ddf301c", "company": "Webster & Webster Associates", "job_status": 2, "isActive": 1, "updatetime": ...}`
  - **Indexes**: `employerId_1_clientJobId_1`, `company_1_employerId_1_job_status_1`, `updatetime_1`, `isActive_1`.
- **`ETL_AUD_Data` Sample Doc**: `{"title": "Account Manager", "company": "Recruitics", "Type": 1, "employerId": "6087e5b9a780b204f8c88645", "clientJobId": "4785500004"}`
  - **Index**: `employerId_1_Type_1` (`Type == 1` = new/active candidate, `Type == 0` = feed-expired!).

---

### F. Central Hub Control & Output Collections (`<CENTRAL_VPS_IP>`)
- **`daily_stats.input`**: `{"Domain": "championwindow.com/gfj", "DomainType": "Proxy", "employerId": "5f16b7fba780b2085c230ea1"}`
- **`daily_stats.output`**:
```json
{
  "_id": "ObjectId(6aba5b95605b9e50947e62b0)",
  "Date": "ISODate(2026-09-28T00:00:00Z)",
  "Domain": "gfj.lettuce.com/",
  "employerId": "emp-jbk-lettuce",
  "Company": "Lettuce Entertain You Restaurants",
  "DomainType": "Direct Apply",
  "To_Post": 5814,
  "FeedExpiredJobs": 532,
  "LiveGeneratedAt": "ISODate(2026-09-28T12:20:37.925Z)",
  "Posted_Jobs": 100,
  "Updated_Jobs": 0,
  "Reposts": 0,
  "Cache_Updated_Jobs": 0,
  "Posted_Bot": 100,
  "Expired_Jobs": 0,
  "Expires_Bot": 0,
  "DB_Clicks": 5,
  "Bot_Visits": 514,
  "Posting_Queue": 5,
  "Expires_Queue": 0,
  "Post_Fail": 0,
  "Expires_Fail": 0,
  "To_Expire_In_5Days": 0,
  "Total_Posted_Jobs": 502,
  "Total_Expired_Jobs": 0,
  "WindowStart": "ISODate(...)",
  "WindowEnd": "ISODate(...)",
  "GeneratedAt": "ISODate(2026-09-29T03:30:02.533Z)"
}
```
- **`daily_stats.oldstats`**: Same schema as closed `output` doc, indexed on `Domain_1_employerId_1_Date_1` and `Domain_1_Date_1`.
- **`daily_domain_stats.stats`**: Indexed on `date_domain`, `date_only`, `date_key` (`Date` + `Key`).
- **`jobicarenode_prod.Target_P4_Opt`**: Upstream Proxy feed/staging collection using `emp-jicn-*` employer IDs (`emp-jicn-hcsg`, `emp-jicn-abs`, `emp-jicn-qrm`, `emp-jicn-concentrix`, `emp-jicn-yescommunities`). Links to `prod_jobiak_ai.job` via **`uniqueKey == clientJobId`**, and carries **`extraInfo.feedData`** (`1` = Feed job, `0` = Expanded job).
- **`data_cleansing.ETL_Job_Log`**: ETL execution audit collection (`{"employerId": "6a90...", "data.clientJobId": "..."}`) checked before pushing ready-to-post Proxy jobs.
- **`prod_jobiak_ai.jobiak_keyword_Updation`**: Keyword rule collection for Proxy employers (`employerId`, `title`, `keyword`, `keywordType`, `operatorType` [`contains-title` / `equals-title`], `isActive`, `companyName`).
- **`domain_postings.domains`**: `{"Domain": "earnhaus.com/gfj", "Domain Type": "Proxy", "Quota": 5000, "EmployerId": "68b8133b060e8f5df1a6c3a7"}`.
- **`GenAI.faq`**: `{"Name": "Dixit", "Job Title": "...", "faq": "...", "AI": "write a 50 words...", "ai_response": "<p>...</p>", "status": "completed"}` — indexed on `status_1_ai_response_1`.
- **`generateXml_prod.emp-gxc-*`**: 396+ collections with fields `title`, `location`, `city`, `state`, `company`, `cpa`, `cpc`, `employerId`, `feedData` — 39 indexes including `company_1_employerId_1`, `cpa_1`, `cpc_1`. *(Always access via `db.get_collection(name)` because some feed collection names contain trailing dots.)*

---

## 5. Google Views/Clicks & Bot Traffic Filtering Logic (Exact Queries)

**Core Rule:** In Jobiak, **"Views"** and **"Clicks"** both refer to organic human interactions coming from Google for Jobs.

### Pure Human Google Clicks Filter
Every valid human Google click MUST satisfy ALL 4 conditions:
```javascript
// Mongo Shell / Studio 3T
{
  "employerId": "6aa8d214060e8f0b78b0dc87", // Omit for whole Programmatic DB
  "isBot": false,
  "browserType": { "$ne": "Unknown" },
  "deviceType": { "$ne": "Unknown" },
  "isFromGoogle": true,
  "createdDt": {
    "$gte": ISODate("2026-11-10T00:00:00.000Z"),
    "$lt":  ISODate("2026-11-12T00:00:00.000Z")
  }
}
```

### Deduplicated Unique Views vs. Raw Views (Mongo Shell & PyMongo)
- **Raw Views**: Total count of hits matching the filter above.
- **Unique Views (`DB_Clicks`)**: Deduplicated by `(ipAddress, job)` so 1 person refreshing or double-clicking the same job counts as **1**:
```javascript
// Studio 3T / Mongo Shell Aggregation
db.getCollection("userAnalytics").aggregate([
  {
    $match: {
      employerId: "6a904f26060e8f0b78b0dc81",
      isBot: false,
      browserType: { $ne: "Unknown" },
      deviceType: { $ne: "Unknown" },
      isFromGoogle: true,
      createdDt: { $gte: ISODate("2026-11-11T00:00:00Z"), $lt: ISODate("2026-11-12T00:00:00Z") }
    }
  },
  // IMPORTANT: Proxy dailystats uses "$jobId"; Proxy expires/joins use "$childJobId"; Direct/Prog uses "$jobPubJobId"
  { $group: { _id: { ip: "$ipAddress", job: "$jobId" } } },
  { $count: "DB_Clicks" }
], { allowDiskUse: true });
```

### Non-Bot / Bot Traffic Breakdown Query
- **Googlebot / Crawler Visits**: `{"isBot": true, "createdDt": window}`
- **Non-Bot Direct / Non-Google Visits**: `{"isBot": false, "isFromGoogle": false, "createdDt": window}` *(Traffic that didn't carry a Google referrer — often tracked alongside Google Views in client audits like ABS Kids / HCSG / Lettuce!)*

---

## 6. Daily Stats Pipeline (`Stats/dailystats.py` & `dailystats_old.py`) — Complete Deep Dive

### Why & When We Run It
- **Purpose**: Produces the daily operational scorecard for all 15 priority domains in `daily_stats.input` so engineers can see how many jobs are waiting (`To_Post`), posted (`Posted_Jobs`), updated (`Updated_Jobs`), saved via hash cache (`Cache_Updated_Jobs`), crawled by Googlebot (`Posted_Bot`, `Expires_Bot`), clicked by humans (`DB_Clicks`), failed (`Post_Fail`, `Expires_Fail`), or expiring soon (`To_Expire_In_5Days`).
- **How to Run**: `python Stats/dailystats.py` (uses `MAX_WORKERS = 10` threads).
- **Input**: `daily_stats.input` (15 documents).
- **Output**: Upserts **2 documents per domain** into `daily_stats.output` keyed on `(Domain, employerId, Date)`:
  1. **`Date = TODAY (00:00 UTC)`**: Updates **ONLY `LIVE_FIELDS`** (`To_Post`, `FeedExpiredJobs`, `LiveGeneratedAt`). Overwritten every run today because queue sizes change constantly.
  2. **`Date = YESTERDAY (00:00 UTC)`**: Computes all closed 24h metrics over `[yesterday 00:00, today 00:00)`. **Never touches `To_Post` or `FeedExpiredJobs` on yesterday's doc** so yesterday's final snapshot stays intact!

---

### A. Exact Step-by-Step Queries for Regular Domains (Direct Apply & Programmatic)

Let `base = {}` for `Programmatic`, or `{"employerId": {"$in": employer_ids}}` for `Direct Apply`.

1. **`To_Post`** *(Live -> TODAY doc)*:
   ```javascript
   db.Target_P4_Opt.countDocuments({ ...base, gpost: 1, job_status: { $ne: 3 } })
   ```
2. **`FeedExpiredJobs`** *(Live -> TODAY doc)*:
   ```javascript
   db.Target_P4_Opt.countDocuments({ ...base, job_status: 3 })
   ```
3. **`Posted_Jobs`, `Updated_Jobs`, `Reposts`** *(YESTERDAY doc)*:
   ```javascript
   // Change action to "post", "update", or "repost"
   db.Target_P4_Opt.countDocuments({
     ...base,
     action: "post",
     gpost: 5,
     job_status: { $ne: 3 },
     gpost_date: { $gte: WINDOW_START, $lt: WINDOW_END }
   })
   ```
4. **`Google_URL_UPDATED` & `Cache_Updated_Jobs`** *(YESTERDAY doc)*:
   - `Google_URL_UPDATED = db.aj_jp_google_logs.countDocuments({ ...base, callType: "URL_UPDATED", createdAt: window })`
   - `Cache_Updated_Jobs = max((Posted_Jobs + Updated_Jobs + Reposts) - Google_URL_UPDATED, 0)`
   - **Why**: If 500 jobs were marked `posted/updated/reposted` in `Target_P4_Opt` today, but only 350 called Google's `URL_UPDATED` API, the remaining 150 jobs were satisfied by cache without spending Google API quota!
5. **`Posted_Bot`** *(YESTERDAY doc)*:
   - Step 1: Collect `posted_ids = Target_P4_Opt.distinct("jobPubJobId", { ...base, gpost: 5, gpost_date: window })`
   - Step 2: Intersect with `aj_jp_google_logs.distinct("jobId", google_updated_filter)` *(if `Google_URL_UPDATED == 0`, returns `0` immediately)*.
   - Step 3: Count distinct crawled jobs:
     ```python
     len(analytics.distinct("jobPubJobId", {
         "jobPubJobId": {"$in": posted_ids},
         "isBot": True,
         "action": {"$in": ["post", "repost", "update"]},
         "createdDt": window
     }))
     ```
6. **`Expired_Jobs` & `Expires_Bot`** *(YESTERDAY doc)*:
   - `Expired_Jobs = aj_jp_google_logs.countDocuments({ ...base, callType: "URL_DELETED", createdAt: window })`
   - `expired_ids = Target_P4_Opt.distinct("jobPubJobId", { ...base, gpost: 6, gpost_expire_date: window })`
   - `Expires_Bot = len(analytics.distinct("jobPubJobId", {"jobPubJobId": {"$in": expired_ids}, "isBot": True, "action": "expire", "createdDt": window}))`
7. **`DB_Clicks` & `Bot_Visits`** *(YESTERDAY doc)*:
   - `DB_Clicks`: Pure human filter + `$group` on `{"ip": "$ipAddress", "job": "$jobPubJobId"}` + `$count`.
   - `Bot_Visits`: `userAnalytics.countDocuments({ ...base, "isBot": True, "createdDt": window })`
8. **Queues, Failures & Totals** *(YESTERDAY doc)*:
   - `Posting_Queue`: `Target_P4_Opt.count({ ...base, gpost: 3, job_status: { $ne: 3 } })`
   - `Expires_Queue`: `Target_P4_Opt.count({ ...base, gpost: 8 })`
   - `Post_Fail`: `Target_P4_Opt.count({ ...base, gpost: 4, gpostExeOn: { $exists: true } })`
   - `Expires_Fail`: `aj_jp_google_logs.count({ ...base, callType: "URL_DELETED", status_update: 4, createdAt: window })`
   - `To_Expire_In_5Days`: `Target_P4_Opt.count({ ...base, pub_expired: { $lt: today + 5d }, gpost: 5, job_status: { $ne: 3 } })`
   - `Total_Posted_Jobs`: `Target_P4_Opt.count({ ...base, gpost: 5, job_status: { $ne: 3 } })`
   - `Total_Expired_Jobs`: `Target_P4_Opt.count({ ...base, gpost: 6 })`
9. **Programmatic Company Breakdowns**: Only when `DomainType == "Programmatic"`, `get_company_stats()` groups by `(company, employerId)` to store `posted_companies`, `updated_companies`, `cache_updated_companies`, and `expired_companies`.

---

### B. Exact Step-by-Step Queries for Proxy Domains (`prod_jobiak_ai`)

Proxy `job` documents do NOT store an `action` field or `gpost` code, so `get_proxy_stats()` uses cross-cluster queries and a 2-`$lookup` aggregation:

1. **`To_Post` (Cross-Cluster Set Difference)**:
   - Stream `clientJobId` (`batch_size=5000` cursor to avoid Mongo's 16MB `distinct()` limit!) from **`ETL_Scrapping_Data.ETL_Scraping_Data`**:
     `A = { clientJobId | employerId in ids and job_status != 3 }`
   - Stream `clientJobId` from **`prod_jobiak_ai.job`**:
     `B = { clientJobId | employerId in ids and status in ["posted", "removed"] }`
   - **`To_Post = len(A - B)`**.
2. **`FeedExpiredJobs`**:
   - Connects to **`data_cleansing.ETL_AUD_Data`** and counts `{"company": {"$in": variants}, "Type": 0}` *(exact, lower, upper, title, trailing-space)*, falling back to `{"employerId": {"$in": ids}, "Type": 0}`.
3. **4-Way `$switch` Classification Pipeline (`Posted_Jobs`, `Updated_Jobs`, `Reposts`, `Cache_Updated_Jobs`)**:
   ```javascript
   db.getCollection("job").aggregate([
     { $match: { employerId: { $in: ids }, status: "posted", isActive: true, datePosted: { $gte: W_START, $lt: W_END } } },
     // Join all URL_UPDATED Google API logs for this jobId
     {
       $lookup: {
         from: "jobsGoogleSubmittedLog",
         let: { jobId: "$jobId" },
         pipeline: [
           { $match: { $expr: { $and: [{ $eq: ["$jobId", "$$jobId"] }, { $eq: ["$callType", "URL_UPDATED"] }] } } },
           { $project: { _id: 1, createdAt: 1 } }
         ],
         as: "allLogs"
       }
     },
     // Filter logs belonging to Yesterday's 24h window
     {
       $addFields: {
         todayLogs: {
           $filter: {
             input: "$allLogs", as: "log",
             cond: { $and: [{ $gte: ["$$log.createdAt", W_START] }, { $lt: ["$$log.createdAt", W_END] }] }
           }
         }
       }
     },
     // Check if clientJobId ever existed with status "removed" (proves a repost!)
     {
       $lookup: {
         from: "job",
         let: { clientJobId: "$clientJobId" },
         pipeline: [
           { $match: { status: "removed", $expr: { $eq: ["$clientJobId", "$$clientJobId"] } } },
           { $limit: 1 }
         ],
         as: "removedHistory"
       }
     },
     { $addFields: { totalLogCount: { $size: "$allLogs" }, todayLogCount: { $size: "$todayLogs" }, hasRemovedHistory: { $gt: [{ $size: "$removedHistory" }, 0] } } },
     {
       $addFields: {
         classification: {
           $switch: {
             branches: [
               { case: { $and: [{ $gt: ["$totalLogCount", 1] }, { $gt: ["$todayLogCount", 0] }] }, then: "update" },
               { case: { $and: [{ $eq: ["$totalLogCount", 1] }, "$hasRemovedHistory", { $gt: ["$todayLogCount", 0] }] }, then: "repost" },
               { case: { $and: [{ $eq: ["$totalLogCount", 1] }, { $eq: ["$hasRemovedHistory", false] }, { $gt: ["$todayLogCount", 0] }] }, then: "posting" }
             ],
             default: "cache_update"
           }
         }
       }
     }
   ], { allowDiskUse: true });
   ```
4. **Proxy Expires, Bot & Clicks**:
   - `Expired_Jobs`: `job.count({ employerId in ids, status: "removed", isActive: False, updatedAt: window })`
   - `Posted_Bot` / `Expires_Bot`: `analytics.distinct("childJobId", { childJobId: { $in: target_ids }, isBot: True, country: "United States", createdDt: window })`
   - `DB_Clicks`: Pure human Google filter grouped by `{"ip": "$ipAddress", "job": "$jobId"}`.
   - `Total_Posted_Jobs`: `job.count({ employerId in ids, status: "posted", isActive: True })`
   - `Total_Expired_Jobs`: `job.count({ employerId in ids, status: "removed" })`
   - `To_Expire_In_5Days`: `job.count({ employerId in ids, status: "posted", isActive: True, validThrough: { $lt: today + 5d } })`

### C. `Stats/dailystats_old.py` (Historical Backfill into `daily_stats.oldstats`)
- Runs across a fixed historical range (e.g., `2026-08-01` to `2026-11-05`) with `MAX_WORKERS = 3`.
- Skips `To_Post`, `FeedExpiredJobs`, and `To_Expire_In_5Days`.
- Maintains monotonic running cumulative sums for `Total_Posted_Jobs` and `Total_Expired_Jobs` up to each day's `WindowEnd`.

---

## 7. Enterprise Clicks Report Dashboard & API (`pm2-vps/Clicks Report/clicks_report.py`)

- **What & Why**: 157 KB single-file Flask service providing an interactive dark-glow UI, team reporting API, Matplotlib 7-day sparkline charts in emails, and automated sync to Google Sheet `"Domain Stats"`.
- **How to Run**: `PORT=8000 API_KEY=... python clicks_report.py` (or curl `/run` via cron).
- **Per-Employer Keying**: Every row is keyed as **`domain@emp1,emp2`** (or `domain` if blank). Shared lines across multiple teams are queried **once** and reused.
- **Time-Aware `TODAY` Comparison**: When `date=today`, yesterday's delta uses an **exact same-UTC-clock cutoff** *(while printing labels in `REPORT_TZ=Asia/Kolkata` IST)*.
- **Output Storage (`daily_domain_stats`)**:
  - `stats`: Stores `Date`, `Key`, `Domain`, `EmployerId`, `Clicks`, `Unique Clicks`, `PostingsCount`.
  - `previews`: Stores rendered email HTML + inline charts per `(Date, Team)` for instant `/preview` page loading.
  - Writes Google Sheet tabs: **`Master Stats`** (`Date | Team | Domain | Employer ID | Type | Clicks | Unique Clicks | Postings | Expires`) + per-lead tabs (`Dixit`, etc.).

| Endpoint | Method | Key Params | Behavior |
|---|---|---|---|
| `/` & `/health` | `GET` | `?key=` | Web Dashboard UI & health check. |
| `/summary` | `GET` | `date`, `team` | Instant overview served solely from `daily_domain_stats` *(never hits remote DBs)*. |
| `/run` & `/stats` | `GET/POST` | `date=today\|yesterday`, `teams=`, `email=true\|false`, `sheet=true\|false`, `mode=sync\|async` | Executes report, updates MongoDB & Google Sheets, sends emails (or skips emails on `/stats`). |
| `/preview` & `/preview/refresh` | `GET/POST` | `date`, `team`, `raw=true` | Shows cached HTML email preview or triggers async job refresh (`/jobs/<job_id>`). |
| `/diagnose` | `GET` | `date` | Read-only per-line health diagnostics. |

---

## 8. Proxy Export & TargetP4 Audit Microservice (`pm2-vps/Proxy/` & `Proxy/`)

Runs via Uvicorn on port **`8005`** (`pm2-vps/Proxy/api.py`, plus root `Proxy/earnhaus_export_api.py` and `Proxy/proxy_api.py` on port `8000`) to export daily candidate IDs to Google Sheets (`EarnHaus` and `Postings` spreadsheets) with **strict Mutual Exclusion** (zero overlap between Updates, DatePosted, and Expires).

### Endpoint 1: `POST /export` (Earn Haus / Proxy Google Sheets Export)
- **Step 1 (`fetch_updates`)**: Selects `updates` job IDs from `prod_jobiak_ai.job` (`fetch_job_pool`, rolling `validThrough` cutoff, excluding `EXCLUDED_TITLES`).
- **Step 2 (`fetch_datePosted` / Pool Share)**: Takes the immediately following chunk from the same active pool (or strictly excludes `update_ids` + `expire_ids`).
- **Step 3 (`fetch_expires`)**: Rebuilds `domain_expires.{domain}_expires` (`30` days zero-views = active jobs minus Google-viewed jobs), selects `expires` IDs strictly excluding `update_ids` and `datePosted` IDs *(raises `RuntimeError` if any overlap exists!)*.
- **Step 4 (`fetch_postings`)**:
  1. Aggregates **`data_cleansing.ETL_AUD_Data`** (`Type: 1`, `employerId`, `$sample: 50000`, matching high-converting survey/remote titles in `POSTINGS_TITLES`).
  2. Excludes any `clientJobId` already in `prod_jobiak_ai.job`.
  3. Confirms freshness in **`ETL_Scrapping_Data.ETL_Scraping_Data`** (`updatetime >= today UTC` and `job_status != 3`).
- Writes tabs `postings`, `updates`, `expires`, `dateposted`, and appends audit rows to Google Sheets + `proxy_stats.run_logs`.
- **Companion Root Script (`Proxy/updates_postings.py`)**: Checks `prod_jobiak_ai.job` + `ETL_Scrapping_Data.ETL_Scraping_Data` and emails CSV exports via Gmail SSL (`465`).

### Endpoint 2: `POST /targetp4` (`targetp4_handler.py` & `Stats/to_post.py`)
- Reads domain roster from `"Postings"` sheet (`Domains` tab).
- Groups pending jobs in `Target_P4_Opt` (`gpost: 1, job_status != 3`) by `(jobtitle, employerId, company, isRemote, extraInfo.atlExpand)`.
- Cross-references `alternative_desc_change` (`lookupKey = jobtitle=company=employerId`) to flag missing descriptions (`"Desc Not Found"` tab).
- Calls **`IS_REMOTE_API_URL`** (`http://<IS_REMOTE_API_HOST>:5111/update_is_remote` or `http://<IS_REMOTE_API_HOST>:5111/update_is_remote`) to flip `isRemote: TRUE -> false`.
- Writes `"targetp4"`, `"Desc Not Found"`, and `"Stats"` tabs.

---

## 9. Expiring-Soon Alerts & Sliding-Window Updates (`updates.py` & `pub_expired_check.py`)

Both VPS scripts safeguard against sudden active-job drops caused by `pub_expired` / `validThrough` dates expiring:

### A. `pub_expired_check.py` (PM2: `10:15 UTC` daily)
- Checks active jobs expiring within **5 days (`today + 5d`)**:
  - **Proxy**: `{"employerId": emp, "status": "posted", "isActive": True, "datePosted": {"$exists": True}, "validThrough": {"$lt": cutoff_dt}}`
  - **Regular**: `{"pub_expired": {"$lt": cutoff_dt}, "gpost": 5, "job_status": {"$ne": 3}}` *(uses **`hint="pub_expired_1_gpost_1"`** on Programmatic collections to avoid 600s+ full scans!)*.
- Sends Gmail HTML alert (`Action Required: Expiring Jobs Alert`) when expiring counts threaten daily quota.

### B. `pm2-vps/updates.py` (PM2: `09:00 UTC` daily)
- Runs a **10-day sliding-window aggregation** on `Target_P4_Opt` (`hint="pub_expired_1_gpost_1"`) with a **90-day circuit breaker (`MAX_LOOKAHEAD_DAYS = 90`)** to tell the operations team the exact `pub_expired` cutoff date needed to fulfill remaining daily update quota.

---

## 10. Zero-Click Expiration, Feed Reconciliation (`expires.py`), Updates (`updates.py`) & `jobicarenode_prod` Ingestion Collision Check

### A. Universal 30-Day Zero-Click Expiration (`universal_expires.py`, `dc_expires.py`, `newearnhaus_expires.py`, `proxy_expires.py`)
- **Why**: Submitting or keeping thousands of zero-click jobs indexed in Google wastes crawl budget and drags down domain-level CTR/visibility.
- **How It Works**:
  1. Reads target domain configs from `domain_expires.domains` (or `domain_expires.config_domains` / `ID_MAP`).
  2. Fetches active jobs posted `> 30` days ago:
     - Direct Apply / Programmatic (`Target_P4_Opt`): `{"gpost": 5, "job_status": {"$ne": 3}, "gpost_date": {"$gt": start_date, "$lt": end_date}}`
     - Proxy (`prod_jobiak_ai.job`): `{"employerId": emp_id, "status": "posted", "datePosted": {"$exists": True}}`
  3. Fetches all jobs with organic human Google clicks across `userAnalytics` *(and `userAnalytics_old` in `Stats/dc-expires.py`)* under the Pure Human Google Filter (`isBot: False, isFromGoogle: True, browserType != Unknown, deviceType != Unknown`).
  4. **Rule**: $\text{To Expire} = \text{Posted Jobs} - \text{Google Clicked Jobs}$.
  5. Writes eligible records to `domain_expires.{db}_expires` (or `apexfocusgroup_expires` / `levelsurveys_expires` / `newearnhaus_expires` / `earnhaus_expires`), and `Stats/dc_expires.py` / `dc_expires_mail.py` emails Excel sheets of recent zero-click jobs (`DAYS_AGO = 10`, `LIMIT = 2000`).

### B. Root Feed-to-Prod Reconciliation: `expires.py` (`c:\Users\JOBIAK\Documents\Python\expires.py`)
- **What & Why**: Finds Proxy jobs that are ALREADY marked expired in the upstream Jobicare feed (`jobicarenode_prod.Target_P4_Opt`) yet are STILL live in `prod_jobiak_ai.job` (`status: "posted", isActive: True`), then scores them with Google views before expiring them.
- **Step-by-Step Pipeline & Exact Queries**:
  1. **Query 1 — Feed-Expired Keys (`jobicarenode_prod.Target_P4_Opt`)**:
     ```javascript
     { "employerId": "emp-jicn-hcsg", "job_status": 3, "gpost": 3 } // project uniqueKey
     ```
  2. **Query 2 — Still-Active Production Matches (`prod_jobiak_ai.job`, 500-key batches)**:
     ```javascript
     { "employerId": "6a904f26060e8f0b78b0dc81", "status": "posted", "isActive": true, "clientJobId": { "$in": uniqueKeysBatch } }
     ```
  3. **Query 3 — Direct Job Views (`prod_jobiak_ai.userAnalytics`)**: Matches `childJobId` in matched `jobId`s under `GOOGLE_VIEW_FILTER`.
  4. **Query 4 — Title-Level Fallback Views (`prod_jobiak_ai.userAnalytics`)**: Joins `childJobId -> job.jobId` inside configured `[TITLE_VIEWS_START, TITLE_VIEWS_END)` window and groups by `$jobDetails.title`.
- **Resilience**: Saves per-employer progress in `expiry_run_cache/expiry_results.json` and updates Google Sheets with exponential backoff.

### C. Root Active Update Eligibility: `updates.py` (`c:\Users\JOBIAK\Documents\Python\updates.py`)
- **What & Why**: Inverse of `expires.py` — identifies active `prod_jobiak_ai.job` postings eligible to be **refreshed/updated** because they are NOT feed-expired.
- **Exact Query Diff**:
  ```javascript
  // Exclude expired Jobicare uniqueKeys from prod_jobiak_ai.job
  {
    "employerId": employerId,
    "status": "posted",
    "isActive": true,
    "clientJobId": { "$nin": expiredUniqueKeys }
  }
  ```
- Enriches eligible update jobs with `Job Views` (`childJobId`) and `Title Views` and writes one tab per client in Google Sheets (`Domains` input tab -> client output tabs).

---

### D. Cross-System Feed Staging Reconciliation & Pre-Posting Collision Detection (`jobicarenode_prod` vs `prod_jobiak_ai.job`)
- **What & Why**: When preparing to publish new jobs from Jobicare staging (`jobicarenode_prod.Target_P4_Opt`) to Proxy Production (`prod_jobiak_ai.job`), we must check whether candidate jobs (`gpost in [1, 3]`, `job_status != 3`) already exist in `prod_jobiak_ai.job`.
- **The Core Rule**: **"If these uniqueKeys are already present in `prod_jobiak_ai.job`, WE CANNOT POST!"** Posting them would generate duplicate URLs, confuse Google for Jobs indexing, or resurrect removed/expired listings without fresh ATS data.
- **The Key Mapping**:
  $$\text{jobicarenode\_prod.Target\_P4\_Opt.uniqueKey} \longleftrightarrow \text{prod\_jobiak\_ai.job.clientJobId}$$
  *(In `prod_jobiak_ai.job`, the `clientJobId` field stores the exact normalized `uniqueKey` string, e.g. `cook~~dayton~~oh~~us~~group`healthcare`inc`services`)*.
- **Production Audit Case Study (HCSG Candidate Ingestion)**:
  - Query executed on `jobicarenode_prod.Target_P4_Opt` (`employerId: "emp-jicn-hcsg"`, `job_status != 3`, `gpost in [1, 3]`, across 5 key roles: `Dietary Aide`, `Registered Dietitian`, `Laundry Worker`, `Cook`, `Housekeeper`): **11,350 candidate uniqueKeys**.
  - Reconciled in memory against `prod_jobiak_ai.job` (`employerId: "6a904f26060e8f0b78b0dc81"`, 14,171 total HCSG jobs).
  - **Findings**:
    - **10,301 uniqueKeys ALREADY PRESENT (Cannot Post — 90.8%)**:
      - `posted` & `isActive: True`: **8,068 jobs** (already live in Google for Jobs!)
      - `removed` & `isActive: False`: **2,231 jobs** (previously expired listings)
      - `processing`: **2 jobs** (currently in submission pipeline)
      - Breakdown by role: Housekeeper (2,848), Dietary Aide (2,197), Cook (2,107), Registered Dietitian (1,611), Laundry Worker (1,538).
    - **1,049 uniqueKeys NOT in Production (Available To Post — 9.2%)**:
      - Cook (312), Dietary Aide (239), Laundry Worker (222), Housekeeper (216), Registered Dietitian (60).
- **Ready-to-Run Collision Check Query (PyMongo)**:
  ```python
  from pymongo import MongoClient

  # 1. Fetch candidate uniqueKeys from staging
  jicn_db = client["jobicarenode_prod"]
  candidates = jicn_db.Target_P4_Opt.find(
      {
          "employerId": "emp-jicn-hcsg",
          "job_status": {"$ne": 3},
          "gpost": {"$in": [1.0, 3.0]},
          "jobtitle": {"$in": ["Dietary Aide", "Registered Dietitian", "Laundry Worker", "Cook", "Housekeeper"]}
      },
      {"uniqueKey": 1, "jobtitle": 1, "uncleanedLocation": 1, "_id": 0}
  )
  candidate_map = {j["uniqueKey"]: j for j in candidates if j.get("uniqueKey")}

  # 2. Check collision in Proxy Production
  pj_db = client["prod_jobiak_ai"]
  prod_jobs = pj_db.job.find(
      {"employerId": "6a904f26060e8f0b78b0dc81"},
      {"jobId": 1, "clientJobId": 1, "status": 1, "isActive": 1, "_id": 0}
  )
  prod_keys = {j["clientJobId"]: j for j in prod_jobs if j.get("clientJobId")}

  # 3. Partition: Cannot Post vs Available to Post
  cannot_post = [candidate_map[k] for k in candidate_map if k in prod_keys]
  available_to_post = [candidate_map[k] for k in candidate_map if k not in prod_keys]
  print(f"Collision / Cannot Post: {len(cannot_post)} | Available to Post: {len(available_to_post)}")
  ```

---

## 11. Duplicate Detection (`concentrix_expires.py`), Feed vs Expanded (`feed.py`) & Keyword Postings (`postings.py`)

### A. Duplicate Job Detection & Retention Engine (`concentrix_expires.py`)
- **What & Why**: Prevents keyword cannibalization and wasted Google crawl budget when a Proxy employer (`Concentrix`, `employerId: 6a8871d1060e8f0b78b0dc69`) has multiple active postings for the same role in the same city.
- **How Clustering Works (`are_duplicate_candidates` + Union-Find `find_duplicate_groups`)**:
  1. Fetches all `{"employerId": emp, "status": "posted", "isActive": True}` jobs from `prod_jobiak_ai.job`.
  2. Buckets jobs by **exact normalized location** (only same-city jobs are compared).
  3. Pairs two jobs as duplicate candidates via Union-Find if:
     - Exact normalized title match, **OR**
     - `SequenceMatcher` title similarity $\ge 0.78$, **OR**
     - Shared role family AND (`jaccard >= 0.30` OR token overlap $\ge 0.60$), **OR**
     - No recognized role family AND `jaccard >= 0.60` AND similarity $\ge 0.55$.
- **Decision Rules (`decide_group` — Non-Destructive Recommendations Only)**:
  - If any job in the group has `job_views > 0` $\rightarrow$ decide using `job_views`.
  - If all jobs in the group have `job_views == 0` $\rightarrow$ fall back to `title_views`.
  - **Highest unique count** $\rightarrow$ `ACTIVE` *(Keep)*; **lower count** $\rightarrow$ `EXPIRE` *(Recommend removal)*; **all zero or ties** $\rightarrow$ `REVIEW`.
- **Output**: Google Sheet worksheet `"concentrix - duplicates"` (`DUP-0001`, `Location`, `Job ID`, `Job Title`, `views_used_for_decision`, `view_source`, `Action`, `Reason`).

### B. Feed vs Expanded Job Classifier (`feed.py`)
- **What & Why**: For Proxy clients (`ABS Kids`, `QRM`, `Concentrix`, `HCSG`, `YES! Communities`), reconciles how many active/to-post jobs come from the client's original ATS **Feed** vs Jobiak **Location/Title Expansions** — AND catches duplicate or conflicting `uniqueKey` records in `jobicarenode_prod.Target_P4_Opt`.
- **Classification Rule on `extraInfo.feedData`**:
  - `feedData == 1` $\rightarrow$ **Feed Job**
  - `feedData == 0` (or missing in older records) $\rightarrow$ **Expanded Job**
  - Mixed values (`{0, 1}`) sharing the same `uniqueKey` $\rightarrow$ **Conflicting Record**; extra rows with same `(uniqueKey, feedData)` $\rightarrow$ **Duplicate Record**.
- **Exact `To_Post` Audit Query (`jobicarenode_prod.Target_P4_Opt`)**:
  ```javascript
  {
    "employerId": jicnEmployerId,
    "job_status": { "$ne": 3 },
    "gpost": { "$in": [1, 3] },
    "uniqueKey": { "$nin": postedProdClientJobIds }
  }
  ```

### C. Keyword-Qualified Postings Discovery (`postings.py`) & `earnhaus/` Hygiene Scripts
- **`postings.py` (Root)**:
  1. Groups normalized `jobtitle` values from `data_cleansing.ETL_Job_Log`.
  2. Fetches active keyword rules from `prod_jobiak_ai.jobiak_keyword_Updation` (`isActive: True`) supporting `contains-title` (word-boundary regex `\b...\b`) and `equals-title`.
  3. Validates **both** JobiCare title and scraped title (`ETL_Scrapping_Data`) match the keyword rule, keeping the latest `updatetime`.
  > [!WARNING]
  > **Known Bug in `postings.py` (line 38)**: `SCRAPING_COLLECTION` is set to `"ETL_Scrapping_Data"` (double `p`), whereas the live Mongo collection name is **`"ETL_Scraping_Data"`** (single `p`). Always fix to `"ETL_Scraping_Data"` before running!
- **`earnhaus/` Ready-to-Post, QRM & HTML Fixer Suite**:
  - `run_hcsg_gpost1_3.py`: Finds HCSG target titles (`Dietary Aide`, `Registered Dietitian`, `Laundry Worker`, `Cook`, `Housekeeper`) in `jobicarenode_prod.Target_P4_Opt` (`gpost in [1, 3], job_status != 3`), excludes already-posted `clientJobId`s in `prod_jobiak_ai.job`, and excludes queued `data.clientJobId`s in `data_cleansing.ETL_Job_Log`.
  - `process_target_p4.py`: Allocates balanced samples across QRM clinical titles (`PTA`, `COTA`, `SLP`, `OT`, `PT`), filtering out `"$0 - $0"` placeholder salaries.
  - `apply_all_fixes.py`, `process_qrm_fixes.py`, `scan_recruiter_details.py`, `test_city_state.py`: Strips broken HTML tags (`<strong><strong>`, unclosed `<strong>`), removes recruiter emails/names, and validates `"City, ST"` presence inside descriptions.

---

## 12. Root Workspace Client Analytics: HCSG, Lettuce, ABS Kids, QRM, YES Communities, Day-1 Reports & XML Comparison

This section contains the comprehensive, self-contained technical specifications, queries, join algorithms, and execution pipelines for every major client analytics engine across the Jobiak workspace. All queries and pipelines are explained directly below with exact schemas and logic.

---

### A. Healthcare Services Group (HCSG) Production Analytics & Issue Attribution (`hcsg.py` & `issue.py`)

#### 1. Master Posting & Feed Topology
- **Client Identifiers**:
  - Production DB: `prod_jobiak_ai.job` (`employerId: "6a904f26060e8f0b78b0dc81"`)
  - Staging DB: `jobicarenode_prod.Target_P4_Opt` (`employerId: "emp-jicn-hcsg"`)
  - Feed XML DB: `generateXml_prod` (`collection: "emp-gxc-hcsg"`)
- **Master Posting Breakdown**:
  - Total Feed Jobs: **1,952** in client XML feed (`emp-gxc-hcsg`); **1,534** active in Jobicare staging (`job_status != 3`, `extraInfo.feedData == 1`).
  - Total Unique Feed Titles: **98 unique titles** in client XML feed; **86** active in Jobicare.
  - GEO-Expanded Inventory: **16,500 active listings** in Jobicare staging (`job_status != 3`, `extraInfo.feedData == 0`; 35,125 cumulative records).
  - Production Live Jobs (`prod_jobiak_ai.job`): **10,398 currently active live jobs** on Google (`status: "posted"`, `isActive: True`):
    - Feed Jobs: **1,017 (9.78%)**
    - GEO-Expanded Jobs: **9,381 (90.22%)**
  - Core Performing Titles: Over 90% of all traffic and active listings concentrate in 6 core frontline roles: *Cook, Dietary Aide, Floor Tech, Housekeeper, Laundry Worker, Registered Dietitian*.

#### 2. Multi-Alias Analytics Join Logic (`hcsg.py`)
In `prod_jobiak_ai.userAnalytics`, click and view events can reference jobs through multiple legacy fields: `childJobId`, `jobId`, `jobPubJobId`, or `clientJobId`. If an analytics script joins strictly on `jobId`, up to 35% of valid Google views are lost!
- **The Solution**: Build a multi-alias in-memory lookup dictionary from `prod_jobiak_ai.job`:
  ```python
  alias_map = {} # any alias -> canonical jobId
  for j in db.job.find({"employerId": "6a904f26060e8f0b78b0dc81"}, {"jobId": 1, "clientJobId": 1, "jobPubJobId": 1}):
      jid = j["jobId"]
      alias_map[jid] = jid
      if j.get("clientJobId"):
          alias_map[j["clientJobId"]] = jid
      if j.get("jobPubJobId"):
          alias_map[j["jobPubJobId"]] = jid
  ```
- **Date Derivation Rule**: Month and date are extracted from `viewDate`, falling back to `createdDt`. Unmatched records are placed into a dedicated `"Unmatched Analytics"` bucket rather than silently dropped.
- **Month-over-Month (MoM) Metric Calculation**:
  $$\text{MoM \% Change} = \frac{\text{Current Month Views} - \text{Prior Month Views}}{\text{Prior Month Views}} \times 100$$
- **Data Quality Audit**: Scans for duplicate `uniqueId` or `clientJobId` values in production and writes an automated alert tab in the Google Spreadsheet.

#### 3. Before vs. After Event Attribution (`issue.py`)
When traffic drops or feed ingestion changes on an exact date (`ISSUE_DATE`, e.g. `2026-10-24`), `issue.py` partitions the catalog and analytics into two distinct time windows:
- **Metrics Evaluated Before vs After**:
  1. Active Posted Jobs vs Expired Jobs count.
  2. Distinct locations with active listings vs distinct locations generating views.
  3. Location View Penetration: $\frac{\text{Locations with Views}}{\text{Total Active Locations}}$.
  4. Identifies whether traffic loss was caused by job expirations or click velocity drops on existing listings.

#### 4. 6-Tab View & Bot Analysis Engine (`generate_hcsg_views_excel.py`)
Generates a formatted multi-tab workbook (`HCSG_Views_and_No_Bot_Analysis.xlsx`) combining:
- **Pure Human Google Views**: `isFromGoogle: True, isBot: False, browserType != 'Unknown', deviceType != 'Unknown'`.
- **Googlebot Crawl Telemetry**: `isBot: True` and userAgent matching Googlebot.
- **The 6 Output Tabs**:
  1. `HCSG Overview`: Executive KPIs (Total jobs, active posted, expired, total Google views, Googlebot crawls).
  2. `Title Wise`: Rollup of views and bot visits per job title.
  3. `Location Wise`: State and city-level view volume and crawler penetration.
  4. `Title + Location`: Full combination breakdown with active job counts.
  5. `Posted No Bot`: Active posted listings that Googlebot has **never crawled** (identifies indexing bottlenecks).
  6. `All Active Posted`: Complete catalog of currently live listings.

#### 5. Zero-View Active Job Audit (`export_hcsg_no_views.py`)
Exports all `status: "posted", isActive: True` jobs that have captured **0 Google Views**, categorizing them into:
- **Googlebot VISITED**: Google crawled the page, but Google for Jobs chose not to rank it, or searchers did not click. Focus: SEO title optimization and keyword enrichment.
- **Googlebot NEVER VISITED**: Google has not crawled the URL yet. Focus: Sitemap inclusion and Google Indexing API submission.

---

### B. Lettuce Direct Apply Subdomain Analytics & Keyword Resolution (`generate_lettuce_views_excel.py` & `generate_lettuce_keywords.py`)

#### 1. Subdomain Architecture & Database Contract
- **Target Subdomain**: `gfj.lettuce.com`
- **Database**: `directclients_prod` (Shared Direct Apply cluster: `<DIRECT_APPLY_CLUSTER_IP>:27017`)
- **Employer Filter**: `{"employerId": "emp-jbk-lettuce"}` (MANDATORY: `directclients_prod` hosts dozens of subdomains!)
- **Active Job Filter**: `{"employerId": "emp-jbk-lettuce", "gpost": 5, "job_status": {"$ne": 3}}`
- **Join Key**: **`jobPubJobId`** (Links `Target_P4_Opt.jobPubJobId` $\longleftrightarrow$ `userAnalytics.jobPubJobId`).

#### 2. 7-Tab Direct Apply Excel Model (`generate_lettuce_views_excel.py`)
Generates a structured workbook analyzing:
1. `Overview`: High-level summary of active vs expired jobs, total Google clicks, bot visits, and device ratios.
2. `Title Wise`: View and bot distribution per job title.
3. `Location Wise`: City and state geographic performance.
4. `Title + Location`: Granular combination matrix.
5. `Posted No Bot`: Active listings where Googlebot has never visited.
6. `All Active Posted`: Full active inventory with public URLs.
7. `Status & Lifecycle Breakdown`: Complete distribution across `gpost` (1=To Post, 3=Queue, 5=Live, 6=Expired) and `job_status` (1/2=Feed Active, 3=Feed Expired).

#### 3. Dynamic Keyword Expansion Engine (`generate_lettuce_keywords.py`)
- **Problem**: In Direct Apply feeds, `Target_P4_Opt.locationKeywords` often contains unexpanded template strings like `"{title} jobs in {city}, {state}"` or `"{title} near me"`. If left unexpanded, Google for Jobs cannot index specific local search queries.
- **The Solution**: Scans all active `gpost: 5` jobs, extracts `city` and `state` from `uncleanedLocation` or `location`, and expands template placeholders dynamically:
  ```python
  def expand_keywords(job):
      city = job.get("city") or extract_city(job.get("uncleanedLocation"))
      state = job.get("state") or extract_state(job.get("uncleanedLocation"))
      title = (job.get("jobtitle") or "").lower()
      expanded = []
      for kw in job.get("locationKeywords", []):
          cleaned_kw = kw.replace("{city}", city).replace("{state}", state).replace("{title}", title)
          expanded.append(cleaned_kw.strip())
      return list(set(expanded))
  ```

---

### C. ABS Kids Date Comparison & View Trajectory Engine (`generate_abskids_analysis.py`)

- **Client Identifiers**: `employerId: "6aa8d214060e8f0b78b0dc87"` in `prod_jobiak_ai.job`.
- **Methodology**: Compares Google views between the all-time peak clicks date and specific baseline dates (`DATE_1_STR` vs `DATE_2_STR`).
- **Variance Matrix**: Computes title-wise and location-wise variances:
  $$\Delta \text{Views} = \text{Views}_{\text{Date 2}} - \text{Views}_{\text{Date 1}}$$
- Distinguishes listings that gained traffic from listings where clicks fell to zero, exporting `ABS_Kids_Views_and_No_Bot_Analysis.xlsx` and `ABS_Kids_Title_Location_Both_Dates.csv`.

---

### D. Enterprise Client 9-Tab Clicks Performance Reports (QRM & ABS Kids)

- **What & Why**: Standardized reporting architecture designed for enterprise client reviews. Produces multi-tab workbooks (`QRM_Clicks_Performance_Report.xlsx`, `ABS_Kids_Clicks_Performance_Report.xlsx`).
- **The 9 Standard Report Tabs**:
  1. `Executive Overview`: High-level KPI cards (Total Google Clicks, Active Listings, Expired Listings, Unique Clicked Jobs, Unique Visitor IPs, Mobile vs Desktop %).
  2. `Title_Location_Detailed`: Full matrix of every title + location combination with active/expired counts, clicks, mobile/desktop split, and first/last click timestamps.
  3. `Title_Wise_Performance`: Title rollups showing performing vs zero-click job counts.
  4. `Location_Wise_Breakup`: State- and city-level performance and visitor counts.
  5. `Daily_Clicks_Breakup`: Day-by-day click trajectory, unique IPs, device split.
  6. `Title_Daywise_Breakup`: Daily click trend for every individual job title.
  7. `Visitor_Location_Breakup`: Geographic origin of applicants (`city`, `region`, `country`).
  8. `Device_and_Browser_Breakdown`: Devices (Mobile/Desktop/Tablet) and browsers (Chrome, Safari, Edge, Firefox).
  9. `Inventory_Status_Audit`: Catalog health audit (`status == 'posted'` & `isActive == True` vs `status == 'removed'`).
- **CRITICAL Query Performance Rule**: In `prod_jobiak_ai.userAnalytics`, **ALWAYS append `.hint('employerId_1')`**!
  ```python
  # Fast (0.8s): Uses compound employer index
  cursor = db.userAnalytics.find(
      {'employerId': emp_id, 'isFromGoogle': True, 'isBot': False},
      {'jobId': 1, 'createdDt': 1, 'ipAddress': 1, 'city': 1, 'region': 1, 'deviceType': 1, '_id': 0}
  ).hint('employerId_1')

  # Slow (>60s timeout): Scans 15M+ unindexed records across all employers
  cursor = db.userAnalytics.find({'employerId': emp_id, 'isFromGoogle': True, 'isBot': False})
  ```

---

### E. YES Communities Peak Day vs. Yesterday Performance & Expiry Attribution Engine

- **Target Client**: YES Communities (`employerId: "6a86c3d7060e8f0b78b0dc66"` in `prod_jobiak_ai.job`).
- **Production Baseline**:
  - Total Jobs: 1,295 (884 Active Posted, 409 Expired/Removed).
  - All-Time Peak Day: **`2026-10-05` (49 clicks)** across 46 unique jobs.
  - October Target Max Day: **`2026-10-19` (48 clicks)** across 41 unique jobs.
  - Recent Velocity: `2026-11-16` (15 clicks), `2026-11-17` (16 clicks).
- **The Expiry Attribution Problem**: When clicks drop from peak (48 &rarr; 16), clients ask: *"Did we expire the performing jobs, or are the jobs still active?"*
- **The Attribution Methodology**:
  1. Extract all jobs clicked on the peak day (`2026-10-19`).
  2. Cross-reference their current state in `prod_jobiak_ai.job`:
     - **Expired Listings (18.8% of drop / 9 clicks)**: 6 specific jobs reached their `validThrough` date between Nov 1 and Nov 7, 2026, and were naturally expired (`status: "removed", isActive: False`). Example: *Office Administrator* in Dearborn, MI drove 4 clicks on 10-19 and expired Nov 7.
     - **Active Listings Experiencing Rank Decline (81.2% of drop / 38 clicks)**: 35 jobs that generated 39 clicks on 10-19 are **STILL ACTIVE AND POSTED** today, capturing 1 click yesterday due to organic Google for Jobs impression shifts.
     - **New Active Gainers (+14 to +15 clicks)**: New active listings (e.g. *Office Administrator* in Corpus Christi, Fishers, Utica) captured traffic yesterday.
- **Single-CSV Breakdown Architecture (`generate_single_csv_breakdown.py`)**:
  Combines all 105 jobs clicked on peak or yesterday into one master CSV (`YES_Communities_Max_Day_vs_Yesterday_Job_Clicks_Breakdown.csv`) featuring:
  `Job ID`, `Title`, `Location`, `Current Status`, `Active Status`, `Is Job Expired?`, `Date Posted`, `Valid Through`, `Clicks (Max Day 10-19)`, `Clicks (Peak 10-05)`, `Clicks (Yesterday 11-17)`, `Clicks (Prior Day 11-16)`, `Clicks Change`, `Performance Impact Category`, `Lifetime Clicks`, `Job URL`.

---

### F. Multi-Perspective Geographic Clicks Analysis (Indianapolis, IN Case Study)

When auditing clicks for a specific city or metro market (e.g. `Indianapolis, IN, US`), analysts must evaluate **two distinct perspectives**:
1. **Perspective A — Clicks on Job Postings located in that City (`job.location == "Indianapolis,IN,US"`)**:
   - 5 total jobs posted for YES Communities in Indianapolis, IN.
   - **14 total lifetime Google clicks** across 10 active dates (85.7% captured by *Office Administrator* `6ab0f04420604203cdb1143b`).
2. **Perspective B — Clicks from Job Seekers / Visitors located in that City (`userAnalytics.city == "Indianapolis"`)**:
   - Job seekers located in Indianapolis generated **148 total Google clicks** across YES Communities listings.
   - These users clicked on Indianapolis jobs (10 clicks) as well as adjacent Indianapolis metropolitan suburbs (138 clicks): Greenwood IN, Avon IN, Greenfield IN, Fishers IN, Beech Grove IN, Plainfield IN, Anderson IN, Zionsville IN, Cicero IN.
3. **Perspective C — Intersection (Indianapolis Job AND Indianapolis Visitor)**:
   - Exactly **10 clicks** where both the job posting and the applicant resided in Indianapolis.

---

### G. Multi-Domain Day-1 Historical Analytics Engine (`generate_lead_clicks_report.py` & `hariprasad.py`)

#### 1. Multi-Worker Year-Wise Day-1 Engine (`generate_lead_clicks_report.py`)
- **What & Why**: Aggregates daily and monthly Google views from Day 1 of publishing to the present across all lead client domains (both Proxy and Direct Apply).
- **Concurrent Architecture**: Instead of running a single slow sequential query over 4+ years of data, it spawns **1 concurrent worker thread per calendar year (2023, 2024, 2025, 2026)**:
  ```python
  from concurrent.futures import ThreadPoolExecutor

  def fetch_year_data(domain_info, year):
      start_dt = datetime(year, 1, 1, tzinfo=timezone.utc)
      end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
      # Query userAnalytics for that exact year window...
      return year_counts

  with ThreadPoolExecutor(max_workers=4) as executor:
      futures = [executor.submit(fetch_year_data, domain, y) for y in [2023, 2024, 2025, 2026]]
  ```
- **Output Metrics**:
  - Vertical Month-by-Month Views table.
  - All-time single-day Max Clicks count and the exact calendar date it occurred.
  - Prior day / yesterday click volume.

#### 2. Dual-Collection Direct Apply Sum (`hariprasad.py`)
- **The Historical Problem**: In `directclients_prod`, older analytics events were archived into companion collections (`userAnalytics_prod` and `userAnalytics_old`) to keep the primary `userAnalytics` collection lightweight. If an analytics script only queries `userAnalytics`, all pre-archive views are missing!
- **The Solution**: For every Direct Apply domain, query both collections and sum their daily views together:
  $$\text{Total Daily Views} = \text{Views}(\text{userAnalytics}) + \text{Views}(\text{userAnalytics\_prod})$$
- **Scale**: Runs across 15 Direct Apply + 14 Proxy domains simultaneously using a 29-worker pool, formatting results into the master Google Spreadsheet.

---

### H. Cross-Feed XML Comparison & Pricing Analytics (`compare_emp_gxc_feeds.py`)

- **Target Database**: `generateXml_prod` (XML Feed Server: `<XML_FEED_CLUSTER_IP>:27017`).
- **Inventory**: Hosts **396+ XML feed collections** (`emp-gxc-*`) representing partner feeds (e.g. Albertsons, Gopuff, DoorDash, Uber, Grubhub).
- **Execution Architecture**: Uses a 20-worker `ThreadPoolExecutor` to scan collections in parallel.
- **Critical PyMongo Safety Rule**: Avoid dot-notation access (`db.col`) on collections with special characters or trailing dots; always use `db.get_collection(col_name)`:
  ```python
  # Safe access across 396 collections
  collection = db.get_collection(col_name)
  cursor = collection.find({}, {"company": 1, "title": 1, "cpa": 1, "cpc": 1, "_id": 0})
  ```
- **Output Deliverables**:
  - Title-wise feed comparison matrix (`emp_gxc_title_wise_feed_comparison.csv`): Benchmarks CPA (Cost Per Acquisition) and CPC (Cost Per Click) across feed partners.
  - Company feed summary (`emp_gxc_company_feed_summary.csv`): Aggregates total active listings, average CPA, and average CPC per employer brand.

---

## 13. Real-Time Telegram Alerts & XML Feed Mutex Lock (`Job-Posting-Alerts`)

Hosted in `saidixitn/Job-Posting-Alerts` on GitHub Actions (and `PythonProject/Alerts/`):

### A. Hourly Posting Velocity Sentinel (`Alerts/posting_alerts.py` — `cron: "0 * * * *"`)
- **Quiet Hours Guard**: Automatically skipped between **`02:30 IST` and `12:30 IST`**.
- Compares current hour (`Hr`), previous hour (`Prev`), total `Posted` today, `Queue` (`gpost: 3, job_status != 3`), and `QuotaLeft` against previous run stored in `domain_postings.domain_state`:
  - **Hard Stop**: If `QuotaLeft <= 0` (quota completed), **suppresses all alerts**.
  - **Alert 1 — Posting / Queue Stalled**: `curr_hr == 0` AND (`curr_posted == prev_posted` OR `curr_queue == prev_queue`).
  - **Alert 2 — Posting Drop > 500**: `prev_hr > 0` AND `curr_hr < prev_hr` AND `(prev_hr - curr_hr) > 500`.
  - **Alert 3 — Push More Jobs *(Admin only, non-Proxy)***: `QuotaLeft - curr_queue >= 5000`.
  - **Alert 4 — Zero Posts This Hour**: `prev_hr > 0` AND `curr_hr == 0`.
- Sends formatted HTML alerts via Telegram Bot API (`https://api.telegram.org/bot{TOKEN}/sendMessage`).

### B. XML Feed Freshness & 10-Minute Distributed Lock (`xml.py` — `cron: "*/30 * * * *"`)
- Sends HTTP `HEAD` requests to XML URLs in `xml_timings.feed_timings` to parse `Last-Modified` timestamps (UTC + IST).
- Uses an **atomic 10-minute distributed lock** in **`xml_timings.feed_update_lock`** (`find_one_and_update` + `$setOnInsert`, purging locks `> 10 mins` old) so parallel threads never double-increment daily refresh counts in `xml_timings.feed_timings_history`.

---

## 14. BigQuery Streaming, Search Console & NDJSON Bulk Exports

1. **Hourly Clicks Streaming (`pm2-vps/bigquery/hourly_views.py` — `0 * * * *`)**:
   - Streams hourly organic Google views into **`surveys-bigquery.All_Domains_Clicks.run_history`** and upserts atomic hourly buckets (`Hourly_Clicks.$.clicks`) in MongoDB to guarantee idempotency on re-runs.
2. **Search Console Ingestion (`pm2-vps/search_console/searchconsole_bigquery.py`)**:
   - Pulls GSC Query/Page/Clicks/Impressions/CTR/Position across `aj_jp_service_accounts`, loads into BigQuery **`keywords-to-titles.useranalytics_data.gsc_output`**, and tracks history in **`GSC.RunHistory`**.
3. **NDJSON Disk-Streaming Bulk Loader (`PythonProject/Big Query/mongo_bigquery_export.py` & `Views Big Query/bigquery_dump.py`)**:
   - Streams millions of Mongo docs line-by-line into local `.jsonl` files (converting `ObjectId` & `datetime` cleanly), executes `load_table_from_file` into **`dixit-464912.Survey_Domains`** (`WRITE_TRUNCATE`), and removes temp files so RAM stays flat.

---

## 15. Revenue & Affiliate Reconciliation (`banana.py`, `whatjobs.py`, `jobget.py`, `earnhaus_prog.py`)

- **Banana (`Revenue/banana.py`, `Revenue/banana_new.py`, `Automation/banana.py`)**: Groups human clicks by `(ipAddress, jobPubJobId)`, syncs `banana_analytics.stats` & Google Sheets with numeric formatting and `sourceEmployerId` resolution (falling back to URL hostname `$split[2]`).
- **WhatJobs & JobGet (`Revenue/whatjobs.py`, `Revenue/jobget.py`, `pm2-vps/pipeline.py`)**: Ingest `.csv` / `.csv.gz` affiliate reports and extract publisher job IDs from outbound click URLs via regex:
  ```python
  m = re.search(r"_(\d{5,})__", str(url)) or re.search(r"(\d{6,})", str(url))
  ```
- **Earn Haus Affiliate Conversions (`PythonProject/Earn Haus/earnhaus_prog.py`)**: Scans `v2valuejobs_prod`, `telecommutehirings_prod`, `justopinionjobs_prod`, and `earnwithwfh_prod` `userAnalytics` for outbound Go2Cloud links:
  ```javascript
  {
    "isBot": false, "browserType": { "$ne": "Unknown" }, "deviceType": { "$ne": "Unknown" },
    "isFromGoogle": true,
    "extraInfo.url": { "$regex": "^https:\\/\\/hyp\\.go2cloud\\.org\\/.*", "$options": "i" }
  }
  ```
  Exports matched revenue events into `earnhaus_revenue.revenue_data`.

---

## 16. GenAI FAQ Engine, Keywords Schemas, ATS Description Quality & Scrape Cleaners

### A. GenAI FAQ & Content Engines (`pm2-vps/proxy_faq.py`, `PythonProject/Gemini/`, `pm2-vps/serper.py`)
- **`proxy_faq.py`**: Uses `GenAI.faq`, `GenAI.proxy`, and `GenAI.api` (15 worker threads, `OPENROUTER_MODEL = "openrouter/free"`) with proxy validation, 300s cooldowns, and pooled HTTP sessions (`pool_maxsize=100`).
- **`PythonProject/Gemini/` (`ollama_desc.py`, `write_desc.py`)**: Local Ollama & Gemini description generators.
- **`pm2-vps/serper.py` & `PythonProject/Scraping Dog API/`**: Google Maps (`google.serper.dev/maps`) and ScrapingDog API scrapers with multi-key rotation on HTTP `401/403/429`.

### B. Keywords Management Rules (Strict Lowercase Titles)
> [!IMPORTANT]
> Every `title` field in keyword collections/CSVs **MUST be lowercase** (e.g. `cook`, `dietary aide`, `housekeeper`, `laundry worker`, `room attendant - hotels & hospitality`, `floor tech`, `registered dietitian`).

- **Schema 1 — All Keywords (14 columns)** (`genericKeywords`, `titleToTitle`, `companyKeywords`):
  `"_id",employerId,city,state,confidenceValue,keyword,keywordType,operatorType,title,isActive,createdAt,createdBy,_class,companyName`
- **Schema 2 — Location Keywords (10 columns)**:
  `"_id",employerId,confidenceValue,keyword,keywordType,operatorType,title,isActive,companyName,createdAt`
  *(Templates: `"{title} jobs in city, state"`, `"{title} jobs near city, state"` expanded per job city/state).*
- **Audited Bold Keywords**: `cook` &rarr; `"Prep cook hiring near me"`, `dietary aide` &rarr; `"Dietary careers"`, `room attendant - hotels & hospitality` &rarr; `"Hospitality careers"`, `housekeeper` &rarr; `"Housekeeper hiring near me"`.

### C. HTML Sanitation & Recruiter Cleaners (`earnhaus/apply_all_fixes.py`, `process_qrm_fixes.py`)
- Collapses duplicate `<strong><strong>` tags, closes dangling `<strong>` tags before `</li>`, scrubs recruiter names/emails, and injects formatted location schemas.

---

### D. Job Description Quality Audit & Production Cleaning Rules (ATS Scrape Artifacts)
- **The Business & SEO Problem**: When scraping client ATS platforms (e.g. UKG / UltiPro for YES Communities, Workday, Taleo, iCIMS, ADP), raw page headers, unclosed HTML elements, scrape timestamps, and applicant diversion links leak into the `description` HTML field in `prod_jobiak_ai.job`.
- **Google for Jobs Penalties**:
  1. **Search Snippet Ruined**: Google uses the first 160 characters of `<JobPosting>.description` to generate the search snippet in Google for Jobs. A listing displaying `"Posted Wednesday, August 26, 2026, 4:00 AM Community Manager..."` immediately looks months old and expired to job seekers searching in November, destroying CTR!
  2. **Stale Content Down-Ranking**: Google's indexing algorithms can misidentify the scraped timestamp as the actual posting date, suppressing visibility.
  3. **Traffic & Application Leak**: Anti-fraud disclaimers stating *"visit client.com/careers directly for confirmed positions"* instruct candidates to bypass Jobiak proxy tracking (`/gfj/`), ruining conversion and completed application tracking!
  4. **HTML Layout Glitches**: Raw un-tagged street addresses hanging after the final `</p>` tag cause CSS margin and rendering bugs on web browsers.

- **The 5 Critical Production Description Issues & Standard Regex Fixes**:
  | Issue | Frequency in Scraped Data | Example Artifact | Cleaning Regex / Logic |
  |---|:---:|---|---|
  | **1. Leading Scrape Timestamps** | 250 jobs (28.3% in YES Communities) | `Posted Wednesday, September 2, 2026, 4:00 AM <p>...` | `re.sub(r'^\s*Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM\|PM)?\s*', '', desc, flags=re.I)` |
  | **2. Rogue Period / Stray Dot Prefix** | 36 jobs (all GroundsKeeper listings) | `<p><strong>.</strong></p><p><strong>Grounds Keeper...` | `re.sub(r'^\s*<p><strong>\s*\.\s*</strong></p>\s*', '', desc, flags=re.I)` |
  | **3. Trailing Un-Tagged Street Addresses** | 198 jobs (22.4% in YES Communities) | `...<p>Hiring Max Rate: 19 USD</p>8401 E Saddlebrook Dr, Charleston SC` | `last_gt = desc.rfind('>'); desc = desc[:last_gt+1].strip()` |
  | **4. Outbound Career Links / Apply Leaks** | 847 jobs (95.8% in YES Communities) | `visit yescommunities.com/careers/ directly...` | `desc.replace('https://www.yescommunities.com/Careers', '').replace('visit yescommunities.com/careers/ directly...', '')` |
  | **5. Appended Pay Type / Rate Tags** | 884 jobs (100% in YES Communities) | `<p><strong>Pay Type:</strong> Hourly</p><p><strong>Hiring Min Rate:</strong> 18 USD</p>` | Move into schema JSON-LD `baseSalary` or clean CSS badge styling. |

- **Production Drop-In Cleaning Function (Python)**:
  ```python
  import re

  RX_POSTED_PREFIX = re.compile(
      r'^\s*Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\s*',
      re.IGNORECASE
  )
  RX_STRAY_DOT = re.compile(r'^\s*<p><strong>\s*\.\s*</strong></p>\s*', re.IGNORECASE)

  def clean_job_description(desc: str) -> str:
      if not desc:
          return ""
      # 1. Strip leading scrape timestamp
      desc = RX_POSTED_PREFIX.sub("", desc)
      # 2. Strip leading stray dot
      desc = RX_STRAY_DOT.sub("", desc)
      # 3. Strip trailing un-tagged text hanging after final >
      last_gt = desc.rfind(">")
      if last_gt != -1 and last_gt < len(desc) - 1:
          tail = desc[last_gt + 1:].strip()
          if tail:
              desc = desc[:last_gt + 1].strip()
      # 4. Remove outbound direct apply URLs diverting from proxy
      desc = desc.replace("https://www.yescommunities.com/Careers", "")
      desc = desc.replace("visit yescommunities.com/careers/ directly for confirmed position openings.", "")
      return desc.strip()
  ```

---

## 17. Production VPS PM2 Ecosystem, Cloud Backups & Cross-Repo Code Quality Audit

Extracted directly from `pm2-vps/pm2_process_list_backup.json` (`/home/dixit/venv/bin/python`):

| PM2 Name | Script / Command | Schedule (UTC) | Purpose |
|---|---|---|---|
| `jobget-api` | `uvicorn main:app --port 8000` | Always Online | JobGet / Proxy API |
| `jobiak_dashboard` | Dashboard backend | Always Online | Main dashboard backend |
| `faq-generator` | `proxy_faq.py` | Always Online | OpenRouter GenAI FAQ generator |
| `pm2-logrotate` | PM2 logrotate | Always Online | Log rotation |
| `mongo-creds-sync` | `/home/dixit/new_creds.py` | `30 0 * * *` | Cluster URI discovery -> `mongo_creds.creds` |
| `mongo-daily-backup` | `backup_system/final_backup.py` | `0 2 * * *` | Google Drive Mongo backup (14-day retention) |
| `expiry-newearnhaus` | `newearnhaus_expires.py` | `30 4 * * *` | New Earn Haus zero-click expiration |
| `expiry-earnhaus` | `/home/dixit/proxy_expires.py` | `30 5 * * *` | Earn Haus 30-day zero-click expiration |
| `expiry-directclients` | `/home/dixit/dc_expires.py` | `30 6 * * *` | Direct Clients 30-day zero-click expiration |
| `daily-updates-report` | `/home/dixit/updates.py` | `0 9 * * *` | 10-day sliding window `pub_expired` email |
| `stats-email-daily` | `/home/dixit/run_stats.sh` | `0 10,15 * * *` | Clicks summary email (`stats_email.py`) |
| `pub-expired-check` | `/home/dixit/pub_expired_check.py` | `15 10 * * *` | 5-day `pub_expired` alert email |
| `Expires-Report-Mail` | `dc_expires_mail.py` | `15 10 * * *` | Direct Client expiry summary email |
| `jobiak-stats-hourly` | `bigquery/hourly_views.py` | `0 * * * *` | Hourly BigQuery click stream |
| `jobiak-postings-sync` | Postings sync | `*/30 * * * *` | 30-minute postings sync |

**GitHub Auto-Backup (`auto_git_backup.sh`)**: `rsync`s `/home/jobiak_dashboard` and `/home/dixit` into `/home/dixit/pm2_backup/`, saves `pip3 freeze` + `pm2 jlist`, and pushes automatically to GitHub.

### Cross-Repo Code Quality Audit & Optimization Blueprint (Actionable Fixes)
Deep inspection across `Python/`, `pm2-vps/`, `vps-automations/`, `Automation/`, and `PythonProject/` uncovered **7 recurring bottlenecks & bugs** to fix whenever touching or refactoring these pipelines:

1. **Collection Typo in `postings.py` (line 38)**:
   - *Bug*: `SCRAPING_COLLECTION = "ETL_Scrapping_Data"` (double `p`) will query a non-existent/empty collection on `ETL_Scrapping_Data`.
   - *Fix*: Must be `ETL_Scraping_Data` (single `p`), matching `dailystats.py` and `pm2-vps/Proxy/config.py`.
2. **Unindexed Full-Collection Scan in `postings.py` (line 471) & Pre-`$lookup` `$match` Gaps**:
   - *Bug*: `postings.py` streams `ETL_Job_Log` across all employers and filters normalized titles in Python; `updates.py` / `concentrix_expires.py` run `$lookup` across `userAnalytics` before filtering `employerId`!
   - *Fix*: Add `"employerId": EMPLOYER_ID` inside the first `$match` stage of `fetch_title_view_counts` BEFORE `$lookup` + `$unwind` (reduces scan volume by >90%), and add `employerId` + regex pre-filter to `ETL_Job_Log`.
3. **Numeric vs String Type Drift on `Target_P4_Opt` (`gpost` / `job_status`)**:
   - *Bug*: `newearnhaus_expires.py` (lines 49–50) queries `"job_status": {"$ne": "3.0"}, "gpost": 5.0` while live documents hold integer `gpost: 5, job_status: 2` (or float `3.0`).
   - *Fix*: Standardize filters across all expiry scripts to `{"gpost": {"$in": [5, 5.0]}, "job_status": {"$nin": [3, 3.0, "3", "3.0"]}}`.
4. **Hardcoded Credentials & Missing URI Encoding**:
   - *Risk*: `pm2-vps/proxy_expires.py` (line 24) hardcodes a plaintext `mongodb://...` URI, while ~40 scripts copy-paste `MongoClient(doc["mongo_uri"])` without `quote_plus` encoding (which breaks whenever passwords contain `$`, `^`, `*`, `!`).
   - *Fix*: Replace inline connection blocks with a single shared `db_helper.py` (`load_dotenv()` + `safe_encode_uri()` + `maxPoolSize=100`).
5. **Unpooled `MongoClient` Spawning & Unclosed Connections**:
   - *Bug*: `Proxy/updates_postings.py` (`get_mongo_uri()`) and helper functions inside `Revenue/` open a new `MongoClient(MONGO_URI)` per function call without closing or pooling.
   - *Fix*: Reuse module-level pooled `MongoClient` singletons (`_CLIENT_CACHE` keyed by URI) or context managers.
6. **Code Duplication & 0-Byte Dead Files Across Repos**:
   - *Clutter*: Multiple divergent copies exist for `clicks_report.py` / `clicks_service.py` / `clicks_servicee.py` / `clicks_service_old.py`, `banana.py` (3 repos), `Proxy/` vs `pm2-vps/Proxy/`, and empty 0-byte stubs (`pm2-vps/schemas.py`, `PythonProjec/jobiak_dashboard/database_utils.py`, `PythonProjec/stats/dc_clicks.py`).
   - *Fix*: Consolidate shared config/query helpers into one module per service and archive `*_old.py` / 0-byte files.
7. **Dual Analytics Collections in `directclients_prod`**:
   - *Gotcha*: Some historical Direct Apply views live in `userAnalytics_old` (`Stats/dc-expires.py`) or `userAnalytics_prod` (`antigravity/hariprasad.py`), while live clicks write to `userAnalytics`. Reports needing lifetime views should explicitly union `userAnalytics` + `userAnalytics_prod` / `userAnalytics_old`.

---

## 18. Master Engineering Dictionary (A–Z)

- **`action`**: Field in `Target_P4_Opt` (`"post"`, `"update"`, `"repost"`) indicating the publishing event; also in `userAnalytics` for bot crawls (`"post"`, `"update"`, `"repost"`, `"expire"`).
- **`atlExpand` / `locExpand` / `tlExpand` / `mtlExpand`**: Title/location expansion flags inside `Target_P4_Opt.extraInfo`.
- **`Cache_Updated_Jobs`**: Jobs marked posted/updated/reposted without consuming a Google `URL_UPDATED` Indexing API quota call (hash unchanged).
- **`callType`**: Google Indexing API log type (`"URL_UPDATED"` to index/refresh, `"URL_DELETED"` to de-index).
- **`childJobId` / `jobId` / `jobPubJobId`**: Cross-collection job join keys (`job.jobId` <-> `userAnalytics.childJobId` / `jobId` in Proxy; `Target_P4_Opt.jobPubJobId` <-> `userAnalytics.jobPubJobId` in Regular).
- **`clientJobId`**: Upstream client ATS requisition ID — links `ETL_Scraping_Data`, `ETL_AUD_Data`, `jobicarenode_prod.Target_P4_Opt.uniqueKey`, and `prod_jobiak_ai.job`.
- **`DB_Clicks` (Views)**: Pure human organic clicks from Google Search (`isBot: False, isFromGoogle: True, browserType != Unknown, deviceType != Unknown`), deduplicated by `(ipAddress, job)`.
- **`ETL_AUD_Data`**: Audit cleansing collection in `data_cleansing` (`Type: 1` = active posting candidates; `Type: 0` = feed-expired removals).
- **`ETL_Job_Log`**: Execution audit collection in `data_cleansing` storing `data.clientJobId` for jobs already sent through ETL.
- **`ETL_Scraping_Data`**: Raw feed collection inside DB `ETL_Scrapping_Data` (two `p`s in DB name, one `p` in collection name).
- **`feedData`**: Integer flag inside `jobicarenode_prod.Target_P4_Opt.extraInfo` (`1` = original ATS Feed job; `0` = Expanded job).
- **`FeedExpiredJobs`**: Jobs removed by the client's ATS feed (`job_status == 3` in Regular; `Type == 0` in `ETL_AUD_Data` for Proxy; `job_status: 3, gpost: 3` in `jobicarenode_prod`).
- **`gpost`**: Google indexing integer status (`1`=To Post, `3`=Posting Queue, `4`=Post Fail, `5`=Posted Live, `6`=Expired, `8`=Expires Queue).
- **`isActive` & `status`**: Proxy live-status pair in `prod_jobiak_ai.job` (`status: "posted"` + `isActive: true` = active; `status: "removed"` = expired).
- **`job_status`**: Feed status flag (`3` = deleted from feed; `!= 3` = still present in feed).
- **`jobiak_keyword_Updation`**: Collection in `prod_jobiak_ai` holding `contains-title` / `equals-title` keyword rules for Proxy employers.
- **`jobicarenode_prod`**: Staging/feed Target_P4 DB for Proxy employers (`emp-jicn-*`), bridging to `prod_jobiak_ai.job` via `uniqueKey == clientJobId`.
- **`LIVE_FIELDS`**: `{"To_Post", "FeedExpiredJobs"}` — metrics written only to `TODAY`'s doc in `daily_stats.output`.
- **`pub_expired` / `validThrough`**: Google Jobs expiration cutoff timestamp (`Target_P4_Opt` uses `pub_expired`; `prod_jobiak_ai.job` uses `validThrough`).
- **`Quiet Hours`**: `02:30 IST` to `12:30 IST` window during which Telegram posting alerts pause.
- **`status_update`**: Indexing log code in `aj_jp_google_logs` (`4` = failure).
- **`Union-Find Duplicate Clustering`**: Graph-grouping algorithm in `concentrix_expires.py` pairing same-city active jobs via title similarity (`>= 0.78`), Jaccard overlap, and role families (`ACTIVE` winner vs `EXPIRE` / `REVIEW`).
- **`uniqueKey` / `main_uniqueKey`**: Backtick/tilde-delimited composite deduplication string (`"title~~city~~state~~country~~company"`).
- **`userAnalytics_prod` / `userAnalytics_old`**: Companion/historical analytics collections inside `directclients_prod` summed alongside `userAnalytics` in lifetime reports (`hariprasad.py`, `dc-expires.py`).

---

- **`Apply Leak`**: Outbound career URLs or applicant warnings inside job descriptions instructing candidates to bypass Jobiak proxy tracking (`/gfj/`) and visit client root career pages directly.
- **`Pre-Posting Collision Check`**: Querying `prod_jobiak_ai.job` (`clientJobId`) with candidate `uniqueKey`s from `jobicarenode_prod.Target_P4_Opt` to block duplicate or conflicting listings before ingestion.
- **`Scrape Timestamp`**: Plain-text date/time string prepended by scrapers at the start of a description (`"Posted Wednesday, September 2, 2026, 4:00 AM"`), corrupting Google for Jobs snippets.
- **`Trailing Address (Description)`**: Physical street address floating outside HTML tags after the closing `</p>` tag.
- **`validThrough`**: ISO datetime field in `prod_jobiak_ai.job` establishing the schema expiration cutoff; jobs passing this date transition to `status: "removed", isActive: False`.

---

## 19. How to Ask & Standard Execution Playbook

Whenever you ask Antigravity for a report, audit, query, code improvement, or fix, this is the exact execution plan followed from `GEMINI.md`:

| What You Ask | Plan & Execution Steps |
|---|---|
| **"Give me views/clicks + bot analysis for [Client/Employer] for [Dates]"** | 1. Resolve DB via `connect_by_domain_type()` (`prod_jobiak_ai`, `directclients_prod`, or `{slug}_prod`).<br/>2. Run `PURE_HUMAN_GOOGLE_FILTER` (Google Views) + `isFromGoogle: False, isBot: False` (Non-Google Views) + `isBot: True` (Bot Visits) + unique `(ipAddress, job)` deduplication.<br/>3. For historical Direct Apply reports, check if `userAnalytics_prod` / `userAnalytics_old` also hold events.<br/>4. Save `.py` + `.csv`/`.xlsx` cleanly in `antigravity/`. |
| **"Find active jobs with 0 views (or candidates to expire / feed-reconcile) for [Domain]"** | 1. Fetch active jobs (`status: "posted", isActive: True` or `gpost: 5, job_status != 3`) matching `datePosted`/`gpost_date` (or `jobicarenode_prod` `job_status: 3, gpost: 3` -> `clientJobId`).<br/>2. Exclude any job present in `userAnalytics` under `PURE_HUMAN_GOOGLE_FILTER` (plus Googlebot check if auditing zero-crawl jobs).<br/>3. Output CSV with job ID, title, location, bot count, and `submittedUrl`. |
| **"Find duplicate active jobs / Feed vs Expanded breakdown for [Proxy Client]"** | 1. For duplicates: run `concentrix_expires.py` location-bucket + Union-Find similarity logic, comparing direct `job_views` first then `title_views`, outputting `ACTIVE` / `EXPIRE` / `REVIEW`.<br/>2. For Feed vs Expanded: join `prod_jobiak_ai.job.clientJobId` $\leftrightarrow$ `jobicarenode_prod.Target_P4_Opt.uniqueKey` (`extraInfo.feedData`) + `data_cleansing.ETL_Job_Log` exclusions. |
| **"Compare GXC XML feeds in `generateXml_prod` for [Companies]"** | 1. Call `connect_db("generateXml_prod")`.<br/>2. Filter `list_collection_names()` starting with `emp-gxc-`.<br/>3. Access safely via `db.get_collection(col)` (avoids `InvalidName` on trailing dots) using a 20-worker `ThreadPoolExecutor`.<br/>4. Export title-wise CPA/CPC comparison CSV to `antigravity/`. |
| **"Check why postings stopped / debug daily stats / optimize [Script]"** | 1. Inspect `daily_stats.output` (`TODAY` `To_Post`/`FeedExpiredJobs`, `YESTERDAY` `Posted_Jobs`/`Posting_Queue`/`Post_Fail`).<br/>2. Query `aj_jp_google_logs` / `jobsGoogleSubmittedLog` for the last 2 hours and check `pub_expired` (`hint="pub_expired_1_gpost_1"`).<br/>3. When auditing code, check for `ETL_Scraping_Data` spelling, pre-`$lookup` `$match` pushdowns, `db_helper` pooling, and `[5, 5.0]`/`[3, 3.0, "3"]` type safety. |
| **"Generate or expand keywords for [Employer]"** | 1. Force all `title` values to **lowercase**.<br/>2. Resolve `{city}` / `{state}` placeholders in `locationKeywords` if auditing existing docs.<br/>3. Output Schema 1 (14 columns) for `genericKeywords`/`titleToTitle`/`companyKeywords` and Schema 2 (10 columns) for `locationKeywords`. |
| **"Check if jobs in jobicare are already in prod_jobiak_ai (cannot post)"** | 1. Query `jobicarenode_prod.Target_P4_Opt` for candidate uniqueKeys (`employerId: emp-jicn-{client}`, `job_status != 3`, `gpost in [1, 3]`).<br/>2. Query `prod_jobiak_ai.job` for employer's existing `clientJobId`s.<br/>3. Match `uniqueKey == clientJobId`: records present are flagged **CANNOT POST** (break down by `posted`/`removed`/`processing`); records absent are flagged **AVAILABLE TO POST**.<br/>4. Output both CSV and `.txt` lists to `antigravity/`. |
| **"Compare Max Clicks Date vs Yesterday with job-level expiry attribution"** | 1. Fetch all Google clicks from `userAnalytics` using `.hint('employerId_1')` and identify all-time peak day and yesterday.<br/>2. Extract every job clicked on either date.<br/>3. Reconcile with `prod_jobiak_ai.job`: attribute drops between natural job expirations (`validThrough` elapsed -> `status: removed`) vs organic rank decline on active jobs (`status: posted`).<br/>4. Output multi-tab Excel + single master breakdown CSV to `antigravity/`. |
| **"Audit job descriptions for ATS scrape timestamps, rogue dots, and apply leaks"** | 1. Scan `description` across all active jobs (`status: "posted"`).<br/>2. Check leading text before first `<` for `^Posted [Day], [Date], [Time]` regex matches.<br/>3. Check for leading stray dot `<p><strong>.</strong></p>`, trailing un-tagged text after final `>`, and outbound direct career URLs.<br/>4. Export audit CSVs and generate drop-in Python cleaning function. |
| **"Check clicks for a specific city/location for [Client]"** | 1. Query `prod_jobiak_ai.job` for jobs with location in that city -> sum clicks across `userAnalytics` (Perspective A: Job Postings).<br/>2. Query `userAnalytics` where `city == target_city` (Perspective B: Job Seekers / Visitors).<br/>3. Identify intersection (Perspective C) and output day-wise breakdown CSV to `antigravity/`. |
