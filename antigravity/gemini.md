# GEMINI MASTER KNOWLEDGE BASE & COMPLETE OPERATIONS MANUAL
**Jobiak Search Engineering, Multi-Tenant Database Architecture, Analytics Pipelines, Keywords Systems, Job Descriptions Sanitation, Revenue Reconciliation & Complete Operational Code**

---

## 📖 Executive Summary & Comprehensive Sitemap

This document is the unified, definitive master operational manual and architectural reference for the Jobiak Python ecosystem. Every database, collection, schema field, query, bot filter, keywords format, and script across this workspace is documented here with **complete, ready-to-run copy-paste Python code** and exact MongoDB aggregation pipelines.

### Table of Contents
1. [Architectural Overview & Dynamic MongoDB Credential Router](#1-architectural-overview--dynamic-mongodb-credential-router)
2. [The 3 Core Platform Architectures (Proxy, Direct Apply, Programmatic)](#2-the-3-core-platform-architectures)
3. [Master Database & Collection Reference (Full Field Dictionaries)](#3-master-database--collection-reference-full-field-dictionaries)
4. [Views/Clicks vs. Bot Detection Mechanics](#4-viewsclicks-vs-bot-detection-mechanics)
5. [Daily Stats Pipeline (Formulas, Live vs. Closed Windows, Algorithms)](#5-daily-stats-pipeline-formulas-live-vs-closed-windows-algorithms)
6. [Historical Backfill Engine (`dailystats_old.py`)](#6-historical-backfill-engine-dailystats_oldpy)
7. [Keywords Management System (Schemas, Rules, Bold Audits & Expansion)](#7-keywords-management-system-schemas-rules-bold-audits--expansion)
8. [Job Descriptions, HTML Tag Balancers, and Recruiter Cleaners](#8-job-descriptions-html-tag-balancers-and-recruiter-cleaners)
9. [Semrush Audit & Zero-Views Expiration Mechanics](#9-semrush-audit--zero-views-expiration-mechanics)
10. [Revenue Reconciliation (Banana, WhatJobs, JobGet)](#10-revenue-reconciliation-banana-whatjobs-jobget)
11. [Proxy Exporters, Cutoff Engines & FastAPI Services](#11-proxy-exporters-cutoff-engines--fastapi-services)
12. [Reporting Engines: Formatted Excel & Google Sheets Automation](#12-reporting-engines-formatted-excel--google-sheets-automation)
13. [Workspace Scripts Directory & Full File Inventory](#13-workspace-scripts-directory--full-file-inventory)
14. [Ready-to-Run Operational Code Recipes (Do Anything)](#14-ready-to-run-operational-code-recipes)

---

## 1. Architectural Overview & Dynamic MongoDB Credential Router

Jobiak operates across numerous isolated MongoDB clusters (production, scraping, audit, direct clients, programmatic clients, and partner feeds). Instead of hardcoding credentials, the platform uses a **Dynamic Multi-Tenant Credential Registry**.

```mermaid
flowchart TD
    ENV[".env (MONGO_URI)"] --> RootClient["Root MongoClient"]
    RootClient --> CredsCol["mongo_creds.creds (Dynamic Registry)"]
    RootClient --> DailyStats["daily_stats (input / output / oldstats)"]
    
    CredsCol --> Router["Dynamic DB Router: get_database_by_name()"]
    
    Router --> Proxy["Proxy Cluster: prod_jobiak_ai"]
    Router --> DC["Direct Apply / Subdomain: directclients_prod"]
    Router --> Prog["Programmatic Clusters: {client}_prod"]
    Router --> Scraping["Feed Scraping: ETL_Scrapping_Data"]
    Router --> Cleansing["Feed Audit & Expired: data_cleansing"]
    Router --> Jobicare["JobiCare Normalization: jobicarenode_prod"]
    Router --> ProxyStats["Proxy Export Config: proxy_stats"]
    Router --> Revenue["Revenue Data: whatjobs_revenue, jobget_revenue"]
    Router --> ExpAudit["Domain Expires / Semrush: domain_expires"]
```

### The Credential Registry (`mongo_creds.creds`)
1. The bootstrap connection string is loaded from `.env` via `MONGO_URI`.
2. All database connections are resolved dynamically by querying `mongo_creds.creds`:
   ```json
   {
     "domain": "directclients_prod",
     "mongo_uri": "mongodb://user:pass@host:27017/directclients_prod?authSource=admin"
   }
   ```
3. Handles and client connections are cached in-memory with thread locks (`CACHE_LOCK`) to support multi-threading without socket exhaustion.

### Standard Central Connection Router Implementation
```python
import os
import threading
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

DB_CACHE = {}
CLIENT_CACHE = {}
CACHE_LOCK = threading.Lock()

def get_database_by_name(db_name: str):
    """Dynamically resolves a database connection from mongo_creds.creds."""
    with CACHE_LOCK:
        if db_name in DB_CACHE:
            return DB_CACHE[db_name]

    root_client = MongoClient(MONGO_URI, maxPoolSize=100)
    creds_col = root_client["mongo_creds"]["creds"]
    cred_doc = creds_col.find_one({"domain": db_name})

    if not cred_doc:
        # Fallback to local root client
        db = root_client[db_name]
    else:
        uri = cred_doc.get("mongo_uri") or cred_doc.get("uri")
        client = MongoClient(uri, maxPoolSize=100)
        db = client[db_name]
        with CACHE_LOCK:
            CLIENT_CACHE[db_name] = client

    with CACHE_LOCK:
        DB_CACHE[db_name] = db
    return db
```

---

## 2. The 3 Core Platform Architectures

Every client processed in Jobiak falls under one of three distinct architectures:

| Architecture | Primary Job DB | Job Collection | Google Submission Logs | Employer Filter | Examples |
|---|---|---|---|---|---|
| **1. Proxy** | `prod_jobiak_ai` | `job` | `jobsGoogleSubmittedLog` | `{"employerId": {"$in": employer_ids}}` | Healthcare Services Group (`6a904f26060e8f0b78b0dc81`), Concentrix (`6a8871d1060e8f0b78b0dc69`), YES! Communities (`6a86c3d7060e8f0b78b0dc66`), QRM (`6a7b516d060e8f0b78b0dc5a`), ABS Kids (`6aa8d214060e8f0b78b0dc87`), Quality Carriers |
| **2. Direct Apply (Subdomain)** | `directclients_prod` | `Target_P4_Opt` | `aj_jp_google_logs` | `{"employerId": {"$in": employer_ids}}` | Lettuce Entertain You (`emp-jbk-lettuce`), EarnHaus (`68b8133b060e8f5df1a6c3a7`) |
| **3. Programmatic** | `{client}_prod` (dedicated DB) | `Target_P4_Opt` or `{client}_Target_P4_Opt` | `aj_jp_google_logs` | `{}` (Tenant database is dedicated to this client) | Hextill (`hextill_prod`) |

---

## 3. Master Database & Collection Reference (Full Field Dictionaries)

### A. Proxy Architecture (`prod_jobiak_ai`)

#### 1. Collection: `prod_jobiak_ai.job`
Stores primary job postings for all Proxy clients.
- `jobId` *(string)*: Unique primary identifier internal to Jobiak.
- `clientJobId` *(string)*: Unique job requisition ID originating from the client ATS/feed.
- `employerId` *(string)*: 24-character MongoDB hex ObjectId representing the client.
- `title` *(string)*: Published job title.
- `location` *(string)*: Human-readable location string (e.g., `"Philadelphia, PA"`, `"Chicago, IL"`).
- `status` *(string)*: Posting lifecycle status: `"posted"`, `"removed"`, `"expired"`.
- `isActive` *(boolean)*: `true` indicates the job is currently live; `false` indicates inactive.
- `datePosted` *(datetime)*: Timestamp when the job was first published.
- `validThrough` *(datetime)*: Expiration cutoff timestamp on Google Search.
- `submittedUrl` *(string)*: Public URL submitted to Google Indexing API.
- `company` / `companyName` *(string)*: Client company name.

#### 2. Collection: `prod_jobiak_ai.userAnalytics`
Tracks all page visits, Google search views/clicks, and crawler audits.
- `employerId` *(string)*: Client identifier.
- `childJobId` *(string)*: References `job.jobId`.
- `jobPubJobId` *(string)*: Secondary job reference ID (used in clicks and revenue pipelines).
- `isBot` *(boolean)*: `true` for automated crawlers (Googlebot, Bingbot, scrapers), `false` for genuine human users.
- `isFromGoogle` *(boolean)*: `true` if the HTTP referrer originates from Google Jobs Search (`https://www.google.com/`).
- `browserType` *(string)*: Client browser (`"Chrome"`, `"Safari"`, `"Firefox"`, `"Edge"`, `"Unknown"`).
- `deviceType` *(string)*: Client device class (`"Mobile"`, `"Desktop"`, `"Tablet"`, `"Unknown"`).
- `ipAddress` *(string)*: Client IPv4 or IPv6 address.
- `viewDate` / `createdDt` *(datetime)*: Timestamp of the user interaction.

#### 3. Collection: `prod_jobiak_ai.jobsGoogleSubmittedLog`
Execution audit logs from Google Indexing API calls.
- `jobId` *(string)*: References `job.jobId`.
- `callType` *(string)*: `"URL_UPDATED"` (publish or re-crawl) or `"URL_DELETED"` (removal/expiration).
- `createdAt` *(datetime)*: Timestamp when the Google Indexing API request was executed.

---

### B. Direct Apply & Programmatic Architecture (`directclients_prod` / `{client}_prod`)

#### 1. Collection: `Target_P4_Opt`
- `_id` *(ObjectId)*: Unique document MongoDB identifier.
- `employerId` *(string)*: String identifier (e.g. `"emp-jbk-lettuce"`).
- `jobtitle` *(string)*: Job title.
- `location` *(string)*: Formatted location, typically `"City, State"`.
- `locationKeywords` *(array of strings)*: Location keywords supporting dynamic placeholders (`"{city}"`, `"{state}"`).
- `gpost` *(integer)*: Indexing and posting status code:
  - `1`: **To Post** (Ready for Google Indexing submission)
  - `3`: **Posting Queue** (Queued in work pipeline)
  - `4`: **Post Fail** (API submission failed)
  - `5`: **Posted** (Actively indexed on Google Jobs Search)
  - `6`: **Expired** (Removed/de-indexed from Google)
  - `8`: **Expires Queue** (Queued for de-indexing submission)
- `job_status` *(integer)*: Lifecycle flag (`3` = removed from client feed / Feed Expired).
- `action` *(string)*: Last action type performed: `"post"`, `"update"`, `"repost"`.
- `gpost_date` *(datetime)*: Timestamp when posted (`gpost: 5`).
- `gpost_expire_date` *(datetime)*: Timestamp when expired (`gpost: 6`).
- `pub_expired` *(datetime)*: Anticipated expiry cutoff.

#### 2. Collection: `aj_jp_google_logs`
- `jobId` *(string)*: Job ID.
- `callType` *(string)*: `"URL_UPDATED"` or `"URL_DELETED"`.
- `status_update` *(integer)*: Status code (`4` indicates API failure).
- `createdAt` *(datetime)*: API execution timestamp.

#### 3. Collection: `aj_jp_jobqueue`
- Work queue documents for batching URL updates to Google Indexing API.

---

### C. Auxiliary Scraping, Audit & Cleansing Databases

#### 1. `ETL_Scrapping_Data.ETL_Scraping_Data`
*(Notice: DB has double 'p', collection has single 'p')*
- `employerId` *(string)*: Client identifier.
- `clientJobId` *(string)*: Client ATS job identifier.
- `job_status` *(integer)*: `3` = removed from feed.
- `updatetime` *(datetime)*: Timestamp of last feed scrap.

#### 2. `data_cleansing.ETL_AUD_Data`
- Audit log tracking feed removals and changes.
- `company` *(string)*: Client company name.
- `Type` *(integer)*: `0` indicates job removed from feed (used for Proxy `FeedExpiredJobs`).

#### 3. `jobicarenode_prod.Target_P4_Opt`
- JobiCare normalized job feed data. Used in `updates.py` and `feed.py` for feed cross-validation.

#### 4. `proxy_stats`
- `proxy_stats.config`: Active proxy export configurations (`EmployerId`, `Status`, `Company`).
- `proxy_stats.run_logs`: Audit logs for tracking daily exports, SMTP emails, and sync statuses.

#### 5. `daily_stats`
- `daily_stats.input`: Master configuration collection defining all active domains, employerIds, and domainTypes.
- `daily_stats.output`: Production analytics store holding `Date = TODAY` (live snapshots) and `Date = YESTERDAY` (closed 24h metrics).
- `daily_stats.oldstats`: Historical backfill storage (97 consecutive UTC dates per domain).

---

## 4. Views/Clicks vs. Bot Detection Mechanics

In Jobiak analytics, **views and clicks refer to the exact same event**: an organic user interaction with a job listing originating from Google Search.

```mermaid
flowchart LR
    Traffic["Incoming Traffic on Job Listing URL"] --> BotCheck{"isBot == True?"}
    BotCheck -- "Yes" --> Googlebot["Googlebot Crawl / Audit<br/>(Bot Visits / Posted Bot)"]
    BotCheck -- "No" --> QualityCheck{"isFromGoogle == True<br/>& Browser != Unknown<br/>& Device != Unknown?"}
    QualityCheck -- "Yes" --> ValidHuman["Pure Human Google View/Click<br/>(DB_Clicks / Views)"]
    QualityCheck -- "No" --> InternalDirect["Direct / Referral / Internal Traffic<br/>(Excluded from Google Views)"]
```

### The Standard Google Views/Clicks Filter (Pure Human Traffic)
To count genuine organic user views/clicks from Google for reporting and client analytics, use:
```python
GOOGLE_VIEW_FILTER = {
    "employerId": emp_id,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True
}
```

### Googlebot Traffic Filter
To count crawler visits:
```python
GOOGLEBOT_FILTER = {
    "employerId": emp_id,
    "isBot": True
}
```

### Deduplication (Unique IP Views/Clicks per Job)
To eliminate duplicate page refreshes and count unique views/clicks by IP per job:
```python
clicks_pipeline = [
    {
        "$match": {
            **GOOGLE_VIEW_FILTER,
            "createdDt": {"$gte": start_dt, "$lt": end_dt}
        }
    },
    {"$group": {"_id": {"ip": "$ipAddress", "job": "$childJobId"}}},
    {"$count": "count"}
]
```

---

## 5. Daily Stats Pipeline (Formulas, Live vs. Closed Windows, Algorithms)

The daily statistics engine (`Stats/dailystats.py`) runs periodically via PM2 and maintains two distinct documents in `daily_stats.output`:

1. **`Date = TODAY` (Live Snapshot)**: Contains real-time operational metrics that change throughout the day (`To_Post`, `FeedExpiredJobs`).
2. **`Date = YESTERDAY` (Closed Window)**: Contains all historical metrics computed over the strict 24-hour UTC window `[yesterday 00:00:00, today 00:00:00)`.

### Core Metrics Formula Reference

| Metric | Architecture | Database & Collection | Calculation Logic | Target Doc |
|---|---|---|---|---|
| **`To_Post`** | Proxy | `ETL_Scraping_Data` vs `job` | `feed_ids - handled_ids` | `TODAY` |
| **`To_Post`** | Direct / Prog | `Target_P4_Opt` | `gpost == 1 && job_status != 3` | `TODAY` |
| **`FeedExpiredJobs`** | Proxy | `data_cleansing.ETL_AUD_Data` | Docs matching company name with `Type == 0` | `TODAY` |
| **`FeedExpiredJobs`** | Direct / Prog | `Target_P4_Opt` | `job_status == 3` | `TODAY` |
| **`Posted_Jobs`** | Proxy | `job` | `status == 'posted'`, `isActive == True`, `datePosted in window`, `todayLogs.length > 0`, not in removed | `YESTERDAY` |
| **`Posted_Jobs`** | Direct / Prog | `Target_P4_Opt` | `action == 'post'`, `gpost == 5`, `gpost_date in window`, `job_status != 3` | `YESTERDAY` |
| **`Updated_Jobs`** | Proxy | `job` | `status == 'posted'`, `isActive == True`, `datePosted < window.start`, `validThrough in window` | `YESTERDAY` |
| **`Updated_Jobs`** | Direct / Prog | `Target_P4_Opt` | `action == 'update'`, `gpost == 5`, `gpost_date in window`, `job_status != 3` | `YESTERDAY` |
| **`Reposts`** | Proxy | `job` | `status == 'posted'`, `isActive == True`, previously existed in `status == 'removed'` | `YESTERDAY` |
| **`Reposts`** | Direct / Prog | `Target_P4_Opt` | `action == 'repost'`, `gpost == 5`, `gpost_date in window`, `job_status != 3` | `YESTERDAY` |
| **`Google_URL_UPDATED`**| Proxy / Direct | `jobsGoogleSubmittedLog` / `aj_jp_google_logs` | `callType == 'URL_UPDATED'` within window | `YESTERDAY` |
| **`Cache_Updated_Jobs`**| All | Computed | `max((Posted + Updated + Reposts) - Google_URL_UPDATED, 0)` | `YESTERDAY` |
| **`DB_Clicks` (Views)**| All | `userAnalytics` | Organic Google views grouped by `(ipAddress, jobId)` within window | `YESTERDAY` |
| **`Bot_Visits`** | All | `userAnalytics` | All documents where `isBot == True` within window | `YESTERDAY` |
| **`Posted_Bot`** | All | `userAnalytics` | Distinct jobs posted in window that received Googlebot visits | `YESTERDAY` |
| **`Expires_Bot`** | All | `userAnalytics` | Distinct jobs expired in window that received Googlebot removal crawls | `YESTERDAY` |
| **`To_Expire_In_5Days`**| All | `Target_P4_Opt` / `job` | `pub_expired < (today + 5 days)`, `gpost == 5`, `job_status != 3` | `YESTERDAY` |
| **`Total_Posted_Jobs`** | All | `Target_P4_Opt` / `job` | All currently live jobs on Google (`gpost == 5`, `status == 'posted'`) | `YESTERDAY` |
| **`Total_Expired_Jobs`**| All | `Target_P4_Opt` / `job` | Cumulative expired jobs (`gpost == 6`, `status == 'removed'`) | `YESTERDAY` |

---

## 6. Historical Backfill Engine (`dailystats_old.py`)

`Stats/dailystats_old.py` backfills historical data across 97 consecutive days (from `2026-08-01` to `2026-11-05`) into `daily_stats.oldstats`.

### Key Differences from Live Daily Stats:
1. **Iterates Over Date Ranges**: Generates 24-hour UTC chunks `[target_date, target_date + 1 day)`.
2. **Cumulative Total Fields**: For each historical date, `Total_Posted_Jobs` is evaluated as of that exact point in time:
   ```python
   cumulative_posted = jobs.count_documents({
       **base_filter,
       "gpost": 5,
       "gpost_date": {"$lt": target_date + timedelta(days=1)}
   })
   ```
3. **Controlled Concurrency**: Uses `MAX_WORKERS = 3` to prevent socket exhaustion and minimize database CPU impact across client clusters.

---

## 7. Keywords Management System (Schemas, Rules, Bold Audits & Expansion)

Keywords boost organic search rankings across Google Jobs by aligning job titles and locations with common search queries.

> [!IMPORTANT]
> **Strict Rule for Job Titles:**  
> In all keyword collections and files, the `title` field must **always be in lowercase** (e.g., `cook`, `dietary aide`, `housekeeper`, `laundry worker`, `room attendant - hotels & hospitality`, `floor tech`, `registered dietitian`).

### Schema 1: `All Keywords` (General, Title-to-Title, Company Keywords)
Used for `genericKeywords`, `titleToTitle`, and `companyKeywords`.

**Column Headers (14 Fields):**
```csv
"_id",employerId,city,state,confidenceValue,keyword,keywordType,operatorType,title,isActive,createdAt,createdBy,_class,companyName
```

**Field Specifications:**
- `_id`: 24-character hexadecimal MongoDB ObjectId string.
- `employerId`: Target client ObjectId string (e.g. HCSG: `6a904f26060e8f0b78b0dc81`).
- `city`: Leave empty `""` for non-geographic keywords.
- `state`: Leave empty `""` for non-geographic keywords.
- `confidenceValue`: Default `"0d"`.
- `keyword`: Target search phrase (e.g. `"Prep cook hiring near me"`).
- `keywordType`: One of:
  - `genericKeywords` (e.g. `"jobs hiring immediately"`, `"jobs near me"`)
  - `titleToTitle` (e.g. `"Prep cook jobs"`, `"Dietary careers"`)
  - `companyKeywords` (e.g. `"Healthcare Services Group jobs"`, `"HCSG jobs near me"`)
- `operatorType`: `"equals-title"`.
- `title`: Lowercase job title (e.g. `"cook"`).
- `isActive`: `"true"` (boolean string).
- `createdAt`: ISO 8601 UTC timestamp (e.g. `"2026-11-12T00:00:00.000Z"`).
- `createdBy`: Author email (e.g. `"tarun.dammu@jobiak.com"`).
- `_class`: `"ai.jobiak.reports.KeywordLocation"`.
- `companyName`: Quoted company name (e.g. `"healthcare services group, inc"`).

### Schema 2: `Location Keywords` (`locationKeywords`)
Used for geographic keyword expansion.

**Column Headers (10 Fields):**
```csv
"_id",employerId,confidenceValue,keyword,keywordType,operatorType,title,isActive,companyName,createdAt
```

**Field Specifications:**
- `keyword`: Template string containing geographic placeholders, such as:
  - `"{title} jobs in city, state"`
  - `"{title} jobs near city, state"`
  - `"{title} jobs hiring near city, state"`
  - `"{title} jobs near me city, state"`
- `keywordType`: Always `"locationKeywords"`.
- `title`: Lowercase job title.

### Audited Bold Keywords from Master Spreadsheets
When clients request adding new keywords that were highlighted in bold in master sheets (e.g. HCSG), they map directly as follows:

1. **`cook`** &rarr; `"Prep cook hiring near me"` (`titleToTitle`)
2. **`dietary aide`** &rarr; `"Dietary careers"` (`titleToTitle`)
3. **`room attendant - hotels & hospitality`** &rarr; `"Hospitality careers"` (`titleToTitle`)
4. **`housekeeper`** &rarr; `"Housekeeper hiring near me"` (`titleToTitle`)

### Dynamic Location Keyword Expansion (`update_lettuce_keywords_in_db.py`)
For Direct Apply domains like Lettuce (`emp-jbk-lettuce`), jobs in `Target_P4_Opt` store template arrays like:
```json
"locationKeywords": [
  "Prep Cook jobs in {city}, {state}",
  "Cook hiring in {city}, {state}"
]
```
The script reads `location` (`"Chicago, IL"`), extracts `city="Chicago"`, `state="IL"`, replaces the placeholders, and bulk-updates the document using `UpdateOne`:
```python
cleaned_kw = re.sub(r"\{city\}", city, kw, flags=re.IGNORECASE)
cleaned_kw = re.sub(r"\{state\}", state, cleaned_kw, flags=re.IGNORECASE)
```

---

## 8. Job Descriptions, HTML Tags, and Recruiter Cleaners

Scripts in `earnhaus/` analyze and sanitize job descriptions before Google indexing:

1. **Unclosed HTML Tags**:
   Jobs with unclosed `<div>`, `<p>`, or `<span>` tags break Google structured data rendering. Scripts like `apply_all_fixes.py` and `process_qrm_fixes.py` use regex and HTML parsers to balance tags:
   ```python
   # Deduplicate strong tags
   html = re.sub(r'<strong>\s*<strong>', '<strong>', html, flags=re.I)
   html = re.sub(r'</strong>\s*</strong>', '</strong>', html, flags=re.I)
   
   # Fix <li><strong> without closing </strong> before </li>
   html = re.sub(r'(<li>\s*<strong>)(.*?)(</li>)', lambda m: f"{m.group(1)}{m.group(2)}</strong>{m.group(3)}" if '</strong>' not in m.group(2) else m.group(0), html, flags=re.I | re.DOTALL)
   ```

2. **Recruiter Block Replacements**:
   Stale recruiter contact blocks (e.g. `"Contact Sarah at 555-0199"`) are detected via regex in `find_recruiter_names.py` and replaced using templates in `qrm_location_recruiter_replacements.json`.

3. **Missing Location in Description**:
   Google requires the hiring location inside the job body. Scripts in `earnhaus/` cross-check `location` against the HTML description and append sanitized location blocks where missing.

---

## 9. Semrush Audit & Zero-Views Expiration Mechanics

Scripts in `Stats/semrush_urls.py` and `Stats/expires.py` audit URLs against SEO indexing data and handle candidates for de-indexing:

1. **Semrush Whitelist Audit (`Stats/semrush_urls.py`)**:
   - Queries `domain_expires.semrush_url's` cluster.
   - For each live posted URL in `directclients_prod.Target_P4_Opt`, checks if the URL exists in the Semrush organic rank list.
   - Updates `semrush_view_audit` to protect high-ranking Google URLs from accidental expiration.

2. **Zero-Views Job Expiry Engine (`Stats/expires.py`)**:
   - Finds jobs posted for over 30 days (`gpost: 5`, `gpost_date < now - 30 days`).
   - Cross-references `userAnalytics`: identifies jobs that received zero organic Google views/clicks.
   - Excludes any URL present in the Semrush whitelist.
   - Marks zero-performing jobs for expiration queue (`gpost: 8`) to free up indexing budget.

---

## 10. Revenue Reconciliation (Banana, WhatJobs, JobGet)

Scripts in `Revenue/` match user views/clicks against publisher invoices:

1. **Banana Engine (`Revenue/banana.py`)**:
   - Computes daily unique views/clicks by grouping `(ipAddress, jobPubJobId)` over UTC days.
   - Synchronizes unique traffic metrics directly into Google Sheets and MongoDB collections.
   
2. **WhatJobs & JobGet (`whatjobs.py`, `jobget.py`)**:
   - Reads publisher click logs and extracts internal Job IDs via regex:
     ```python
     def extract_jobid(url):
         m = re.search(r"_(\d{5,})__", str(url)) or re.search(r"(\d{6,})", str(url))
         return str(int(m.group(1))) if m else None
     ```
   - Matches publisher clicks with `userAnalytics` to reconcile discrepancies between billable clicks and internal logs.

---

## 11. Proxy Exporters, Cutoff Engines & FastAPI Services

Automated proxy pipelines (`Proxy/updates_postings.py`, `Proxy/proxy_api.py`) run scheduled batch exports:

### 1. The 2,500 / 5,000 Cutoff Algorithm
To prevent overloading Google Indexing API quotas, proxy updates select a date cutoff that yields approximately 2,500 to 5,000 jobs:
```python
def pick_cutoff(results, target_count=2500):
    total = 0
    for r in results:
        total += r["count"]
        if total >= target_count:
            return r["date"]
    return results[-1]["date"] if results else None
```

### 2. FastAPI Export Service (`Proxy/proxy_api.py`)
Provides REST API endpoints for EarnHaus and Proxy exports:
- `POST /export/updates`: Queries active jobs sorted by `validThrough`, exports to Google Sheets.
- `POST /export/postings`: Pulls newly scraped jobs from `data_cleansing.ETL_AUD_Data` not present in `prod_jobiak_ai.job`.
- `POST /export/expires`: Gathers candidates with zero views/clicks and excludes Semrush whitelisted URLs.

---

## 12. Reporting Engines: Formatted Excel & Google Sheets Automation

Jobiak reporting scripts generate professional multi-tab workbooks using `openpyxl` and sync live data via `gspread`:

### Standard OpenPyXL Styling Specification:
```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
thin_border = Border(
    left=Side(style='thin', color='D9D9D9'),
    right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'),
    bottom=Side(style='thin', color='D9D9D9')
)
```

### Generated Workbooks:
- **`generate_client_views_excel.py`**: Outputs 7 structured tabs (Overview, Title Wise, Location Wise, Title + Location Wise, Active Jobs, Status Breakdown, Data Quality) for YES! Communities and QRM.
- **`generate_hcsg_views_excel.py`**: Outputs 7 structured tabs for Healthcare Services Group.
- **`hcsg.py` & `updates.py`**: Real-time bidirectional synchronization with live Google Sheets using Google OAuth Service Accounts (`credentials.json`).

### Healthcare Services Group (HCSG) Job Posting Details & Feed Audit:
**Client Identifiers**: `6a904f26060e8f0b78b0dc81` (Production `prod_jobiak_ai.job`) / `emp-jicn-hcsg` (Upstream `jobicarenode_prod.Target_P4_Opt`) / `emp-gxc-hcsg` (Feed XML `generateXml_prod`)

| Metric | Count | Details / Verification Source |
|---|---:|---|
| **Total Feed Jobs** | **1,952** *(Client Feed)* <br> **1,534** *(Active in Jobicare)* | • `1,952` in Client XML Feed (`generateXml_prod.emp-gxc-hcsg`)<br>• `1,534` active feed jobs in `jobicarenode_prod.Target_P4_Opt` (`job_status != 3`, `extraInfo.feedData == 1`) *(All-time: 3,129)* |
| **Total Unique Feed Count** *(No. of unique titles)* | **98** *(Client Feed)* <br> **86** *(Active in Jobicare)* | • **98 unique job titles** across the 1,952 feed listings in `emp-gxc-hcsg`<br>• **86 unique job titles** across active feed listings in Jobicare *(All-time: 183)* |
| **Total GEO-Expanded Jobs** | **16,500** *(Active)* <br> *(35,125 all-time)* | In `jobicarenode_prod.Target_P4_Opt` with `extraInfo.feedData: 0`<br>• `16,500` active listings (`job_status != 3`)<br>• `35,125` cumulative total records |
| **Number of Feed Jobs Posted** | **1,017** *(Currently Live)* <br> **1,475** *(All-time in Prod)* | In `prod_jobiak_ai.job` (`feedData: 1`):<br>• **1,017** currently active live on Google (`status: 'posted'`, `isActive: True`)<br>• **1,475** total jobs ever handled/published |
| **Number of GEO-Expanded Jobs Posted** | **9,381** *(Currently Live)* <br> **12,474** *(All-time in Prod)* | In `prod_jobiak_ai.job` (`feedData: 0`):<br>• **9,381** currently active live on Google (`status: 'posted'`, `isActive: True`)<br>• **12,474** total jobs ever handled/published |
| **Number of Feed Jobs Remaining to Be Posted** | **532** | Eligible active feed jobs (`job_status != 3`, `gpost in [1, 3]`) not yet present in production *(83 distinct titles ready to post)*.<br>*(738 if excluding only currently live active jobs)* |
| **Number of GEO-Expanded Jobs Remaining to Be Posted** | **7,401** | Eligible active GEO-expanded jobs (`job_status != 3`, `gpost in [1, 3]`) not yet present in production.<br>*(8,830 if excluding only currently live active jobs)* |

- **Total Currently Live Posted Jobs**: **10,398** (Feed: 1,017 [9.78%], GEO-Expanded: 9,381 [90.22%]).
- **Core Live Titles**: Concentrated across 6 core titles: *Cook, Dietary Aide, Floor Tech, Housekeeper, Laundry Worker, Registered Dietitian*.
- **Total Eligible In-Queue to Post**: **7,933** (`532` Feed + `7,401` GEO-Expanded).

---

## 13. Workspace Scripts Directory & Full File Inventory

### Root Directory (`./`)
- **`generate_client_views_excel.py`**: Formatted Excel views/clicks and bot visits workbook generator for YES! Communities and QRM.
- **`generate_hcsg_views_excel.py`**: 7-tab Excel workbook analyzing HCSG Google Job views, bot crawls, and title trends.
- **`generate_lettuce_keywords.py`**: Exports Lettuce jobs with resolved location keywords to CSV.
- **`update_lettuce_keywords_in_db.py`**: Bulk updates `directclients_prod.Target_P4_Opt` to replace `{city}` and `{state}` placeholders.
- **`hcsg.py`**: Live HCSG views and bot analytics sync to Google Sheets.
- **`feed.py`**: Feed audit reconciling JobiCare (`jobicarenode_prod`) vs Production (`prod_jobiak_ai`).
- **`postings.py`**: Validates feed jobs against JobiCare and scraping DB, syncs to Google Sheets "Postings".
- **`updates.py`**: Validates posted active jobs, cross-references JobiCare and analytics, exports updates.
- **`issue.py`**: Audit tool for HCSG views before and after system events.
- **`inspect_bots.py`, `inspect_hcsg_bot.py`, `inspect_ua_fields.py`**: Diagnostic scripts inspecting user analytics headers, user agents, and bot flags.

### Subdirectories
- **`antigravity/`**:
  - `SYSTEM_KNOWLEDGE_BASE.md`: High-level architectural reference.
  - `gemini.md`: This unified operational guide and code cookbook.
  - `db_helper.py`: Dynamic database connection router.
- **`Stats/`**:
  - `dailystats.py`: Daily automated pipeline recording snapshot and closed-window metrics into `daily_stats.output`.
  - `dailystats_old.py`: Historical cumulative backfill engine.
  - `clicks_report.py`: IP grouping and views/clicks analysis.
  - `stats_email.py`: Daily HTML email digest of organic search views/clicks.
  - `semrush_urls.py`: Audits indexed URLs against Semrush whitelist.
  - `expires.py`: Zero-view job expiry candidates.
- **`Proxy/`**:
  - `updates_postings.py`: Automated daily export of Postings (diff between scraped feed and production) and Updates (expiring active jobs), emailed via SMTP.
  - `proxy_api.py`: FastAPI endpoints for proxy metrics.
  - `earnhaus_export_api.py`: EarnHaus job export API.
- **`Revenue/`**:
  - `banana.py`: Unique IP views/clicks reporting into MongoDB and Google Sheets.
  - `whatjobs.py` & `jobget.py`: Revenue reconciliation with publisher partner sheets.
  - `creds.py`: Health check and connection testing across all URIs in `mongo_creds.creds`.
- **`earnhaus/`**:
  - Suite of 50+ scripts for description fixes, recruiter replacements, and HTML sanitation.
- **`pm2-vps/`**:
  - Production cron and PM2 process ecosystem configurations for Ubuntu VPS deployment.

---

## 14. Ready-to-Run Operational Code Recipes

Copy and paste these standalone recipes to perform any standard task immediately.

### Recipe 1: Connect to Any Database Dynamically
```python
import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
root_client = MongoClient(MONGO_URI)

def get_db(db_name: str):
    creds_doc = root_client["mongo_creds"]["creds"].find_one({"domain": db_name})
    if not creds_doc:
        return root_client[db_name]
    uri = creds_doc.get("mongo_uri") or creds_doc.get("uri")
    return MongoClient(uri)[db_name]

# Usage:
prod_db = get_db("prod_jobiak_ai")
dc_db = get_db("directclients_prod")
etl_db = get_db("ETL_Scrapping_Data")
```

---

### Recipe 2: Query Pure Human Views/Clicks for Any Client
```python
from datetime import datetime, timezone

def get_human_views(db, employer_id: str, start_dt: datetime, end_dt: datetime):
    analytics = db["userAnalytics"]
    pipeline = [
        {
            "$match": {
                "employerId": employer_id,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$gte": start_dt, "$lt": end_dt}
            }
        },
        {"$group": {"_id": {"ip": "$ipAddress", "job": "$childJobId"}}},
        {"$count": "total_views_clicks"}
    ]
    res = list(analytics.aggregate(pipeline, allowDiskUse=True))
    return res[0]["total_views_clicks"] if res else 0
```

---

### Recipe 3: Query Googlebot Crawl Visits
```python
def get_bot_visits(db, employer_id: str, start_dt: datetime, end_dt: datetime):
    analytics = db["userAnalytics"]
    return analytics.count_documents({
        "employerId": employer_id,
        "isBot": True,
        "createdDt": {"$gte": start_dt, "$lt": end_dt}
    })
```

---

### Recipe 4: Bulk Update Direct Apply Keywords (Replace `{city}` & `{state}`)
```python
import re
from pymongo import UpdateOne

def expand_location_keywords(dc_db, employer_id="emp-jbk-lettuce"):
    col = dc_db["Target_P4_Opt"]
    cursor = col.find({"employerId": employer_id, "gpost": 5}, {"location": 1, "locationKeywords": 1})
    bulk_ops = []

    for doc in cursor:
        kws = doc.get("locationKeywords")
        if not kws:
            continue
        
        parts = [p.strip() for p in doc.get("location", "").split(",")]
        city = parts[0] if len(parts) > 0 else ""
        state = parts[1] if len(parts) > 1 else ""

        cleaned = [
            re.sub(r"\{state\}", state, re.sub(r"\{city\}", city, kw, flags=re.IGNORECASE), flags=re.IGNORECASE)
            if isinstance(kw, str) else kw
            for kw in kws
        ]

        bulk_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"locationKeywords": cleaned}}))

    if bulk_ops:
        res = col.bulk_write(bulk_ops, ordered=False)
        print(f"Updated {res.modified_count} jobs.")
```

---

### Recipe 5: Calculate Proxy "To Post" (Feed Minus Handled Jobs)
```python
def calculate_proxy_to_post(etl_scraping_col, prod_job_col, employer_ids: list):
    # 1. Fetch current feed clientJobIds
    feed_ids = {
        str(d["clientJobId"]).strip()
        for d in etl_scraping_col.find(
            {"employerId": {"$in": employer_ids}, "job_status": {"$ne": 3}},
            {"_id": 0, "clientJobId": 1}
        ) if "clientJobId" in d
    }

    # 2. Fetch already handled clientJobIds
    handled_ids = {
        str(d["clientJobId"]).strip()
        for d in prod_job_col.find(
            {"employerId": {"$in": employer_ids}, "status": {"$in": ["posted", "removed"]}},
            {"_id": 0, "clientJobId": 1}
        ) if "clientJobId" in d
    }

    # 3. Difference is ready to post
    to_post_ids = feed_ids - handled_ids
    return len(to_post_ids), sorted(list(to_post_ids))
```

---

### Recipe 6: Generate an Insertion-Ready Keyword Record
```python
import bson
from datetime import datetime, timezone

def make_keyword_doc(employer_id: str, company_name: str, title: str, keyword: str, keyword_type="titleToTitle"):
    return {
        "_id": str(bson.ObjectId()),
        "employerId": employer_id,
        "city": "",
        "state": "",
        "confidenceValue": "0d",
        "keyword": keyword,
        "keywordType": keyword_type,
        "operatorType": "equals-title",
        "title": title.strip().lower(),  # Strictly lowercase
        "isActive": "true",
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "createdBy": "tarun.dammu@jobiak.com",
        "_class": "ai.jobiak.reports.KeywordLocation",
        "companyName": company_name
    }
```

---

### Recipe 7: Sanitize Unclosed HTML Tags in Job Descriptions
```python
import re

def sanitize_job_description_html(html_str: str) -> str:
    if not html_str or not isinstance(html_str, str):
        return ""
    
    # 1. Deduplicate strong tags
    cleaned = re.sub(r'<strong>\s*<strong>', '<strong>', html_str, flags=re.I)
    cleaned = re.sub(r'</strong>\s*</strong>', '</strong>', cleaned, flags=re.I)
    
    # 2. Balance <li><strong>...</li> missing </strong>
    cleaned = re.sub(
        r'(<li>\s*<strong>)(.*?)(</li>)',
        lambda m: f"{m.group(1)}{m.group(2)}</strong>{m.group(3)}" if '</strong>' not in m.group(2) else m.group(0),
        cleaned,
        flags=re.I | re.DOTALL
    )
    
    # 3. Fix unclosed <strong> before opening <p>
    cleaned = re.sub(
        r'<strong>(?!.*?</strong>)(.*?)<p>',
        lambda m: f"<p><strong>{m.group(1)}</strong></p><p>" if '</strong>' not in m.group(1) else m.group(0),
        cleaned,
        flags=re.I | re.DOTALL
    )
    
    # 4. Clean dangling </p></p>
    cleaned = re.sub(r'(</p>\s*){2,}', '</p>', cleaned, flags=re.I)
    return cleaned
```

---

### Recipe 8: Full Daily Stats Execution Loop (Single Domain)
```python
from datetime import datetime, timedelta, timezone

def run_single_domain_stats(daily_stats_db, creds_col, domain_name: str, employer_ids: list, domain_type: str):
    output_col = daily_stats_db["output"]
    
    # 1. Connect dynamically
    cred = creds_col.find_one({"domain": domain_name})
    if not cred:
        return
    client = MongoClient(cred.get("mongo_uri") or cred.get("uri"))
    db = client[domain_name]
    
    # 2. Window: [yesterday 00:00:00, today 00:00:00) UTC
    today_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_dt = today_dt - timedelta(days=1)
    window = {"$gte": yesterday_dt, "$lt": today_dt}
    
    if domain_type == "Proxy":
        jobs_col = db["job"]
        analytics_col = db["userAnalytics"]
        logs_col = db["jobsGoogleSubmittedLog"]
        base_filter = {"employerId": {"$in": employer_ids}}
    else:
        jobs_col = db["Target_P4_Opt"]
        analytics_col = db["userAnalytics"]
        logs_col = db["aj_jp_google_logs"]
        base_filter = {} if domain_type == "Programmatic" else {"employerId": {"$in": employer_ids}}
    
    # 3. Aggregate metrics
    posted_count = jobs_col.count_documents({**base_filter, "gpost": 5, "gpost_date": window}) if domain_type != "Proxy" else jobs_col.count_documents({**base_filter, "status": "posted", "isActive": True, "datePosted": window})
    google_urls = logs_col.count_documents({**base_filter, "callType": "URL_UPDATED", "createdAt": window})
    bot_visits = analytics_col.count_documents({**base_filter, "isBot": True, "createdDt": window})
    
    # Human Views/Clicks
    views_res = list(analytics_col.aggregate([
        {"$match": {**base_filter, "isBot": False, "browserType": {"$ne": "Unknown"}, "deviceType": {"$ne": "Unknown"}, "isFromGoogle": True, "createdDt": window}},
        {"$group": {"_id": {"ip": "$ipAddress", "job": "$childJobId"}}},
        {"$count": "c"}
    ], allowDiskUse=True))
    human_views = views_res[0]["c"] if views_res else 0
    
    # 4. Save to daily_stats.output
    output_col.update_one(
        {"domain": domain_name, "Date": yesterday_dt},
        {"$set": {
            "Posted_Jobs": posted_count,
            "Google_URL_UPDATED": google_urls,
            "Bot_Visits": bot_visits,
            "DB_Clicks": human_views,
            "updatedAt": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    print(f"Recorded stats for {domain_name} on {yesterday_dt.strftime('%Y-%m-%d')}.")
```

---

### Recipe 9: Synchronize Metrics to Google Sheets with `gspread`
```python
import gspread
from google.oauth2.service_account import Credentials

def sync_to_google_sheets(spreadsheet_id: str, worksheet_name: str, rows_data: list, creds_file="credentials.json"):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(spreadsheet_id)
    
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=len(rows_data) + 50, cols=len(rows_data[0]) + 5)
    
    ws.clear()
    ws.update("A1", rows_data)
    print(f"Synchronized {len(rows_data)} rows to sheet '{worksheet_name}'.")
```

---

### Recipe 10: Extract Internal Job IDs from Publisher Click URLs
```python
import re

def extract_job_id_from_publisher_url(url: str) -> str:
    """Extracts internal Job IDs from tracking URLs (WhatJobs, JobGet, etc.)."""
    if not url:
        return None
    url = str(url)
    
    # Match pattern: _12345__
    m = re.search(r"_(\d{5,})__", url)
    if m:
        return str(int(m.group(1)))
        
    # Match standalone 6+ digit job IDs
    m = re.search(r"(\d{6,})", url)
    if m:
        return str(int(m.group(1)))
        
    return None
```

---

### 🛡️ Code & Cleanliness Standards for Antigravity

- **Always place new scripts inside `antigravity/`**: Keeps the repository clean and prevents file proliferation in the root.
- **Import from project root**: Use `sys.path.insert(0, os.path.abspath("."))` at the beginning of scripts inside `antigravity/`.
- **Always preserve title lowercase**: When manipulating keyword collections or writing CSV exports, enforce `title.lower()`.
- **Distinguish human views/clicks from bots**: When reporting on performance, always include `isBot: False` and `isFromGoogle: True`.
