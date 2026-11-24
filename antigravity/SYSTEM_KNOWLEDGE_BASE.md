# Jobiak Operations & Architecture Knowledge Base

This document serves as the single source of truth for the database architecture, collections, field dictionaries, query mechanics, keywords formats, bot detection rules, and script inventory across the Jobiak Python ecosystem.

---

## 1. Architectural Overview & Multi-Tenant Database Routing

The system connects to dozens of multi-tenant and single-tenant databases dynamically without hardcoding passwords or hosts.

```mermaid
flowchart TD
    ENV[".env (MONGO_URI)"] --> RootClient["Root MongoClient"]
    RootClient --> CredsCol["mongo_creds.creds"]
    RootClient --> DailyStats["daily_stats (input / output / oldstats)"]
    
    CredsCol --> Router["Dynamic DB Router (get_database_by_name)"]
    
    Router --> Proxy["Proxy Cluster (prod_jobiak_ai)"]
    Router --> DC["Direct Apply / Subdomain (directclients_prod)"]
    Router --> Prog["Programmatic Clusters ({client}_prod)"]
    Router --> Scraping["Scraping Cluster (ETL_Scrapping_Data)"]
    Router --> Cleansing["Cleansing Cluster (data_cleansing)"]
    Router --> Jobicare["JobiCare Cluster (jobicarenode_prod)"]
    Router --> ProxyStats["Proxy Stats (proxy_stats)"]
```

### The Credential Registry (`mongo_creds.creds`)
1. The bootstrap connection is read from `.env` via `MONGO_URI`.
2. Whenever any database is requested (e.g. `directclients_prod`, `prod_jobiak_ai`, `ETL_Scrapping_Data`), the script queries `mongo_creds.creds`:
   ```json
   {
     "domain": "directclients_prod",
     "mongo_uri": "mongodb://user:pass@host:27017/directclients_prod?authSource=admin..."
   }
   ```
3. Handles are cached in-memory with thread-safety (`CACHE_LOCK`) to prevent connection pool exhaustion.

---

## 2. The Three Core Platform Types

| Platform Type | Primary Job Database | Job Collection | Google Submission Logs | Typical Base Filter | Examples |
|---|---|---|---|---|---|
| **Proxy** | `prod_jobiak_ai` | `job` | `jobsGoogleSubmittedLog` | `{"employerId": {"$in": employer_ids}}` | HCSG, Concentrix, YES! Communities, QRM, ABS Kids, Quality Carriers |
| **Direct Apply (Subdomain)** | `directclients_prod` | `Target_P4_Opt` | `aj_jp_google_logs` | `{"employerId": {"$in": employer_ids}}` | Lettuce Entertain You (`emp-jbk-lettuce`) |
| **Programmatic** | `{client}_prod` (dedicated DB) | `Target_P4_Opt` or `{client}_Target_P4_Opt` | `aj_jp_google_logs` | `{}` (all jobs in DB belong to tenant) | Hextill (`hextill_prod`) |

---

## 3. Database & Collection Reference

### A. Proxy Architecture (`prod_jobiak_ai`)
- **`prod_jobiak_ai.job`**:
  - `jobId`: Internal unique job identifier.
  - `clientJobId`: Job identifier from client ATS/feed.
  - `employerId`: Unique client ObjectId (e.g. HCSG: `6a904f26060e8f0b78b0dc81`, Concentrix: `6a8871d1060e8f0b78b0dc69`).
  - `title`: Job title.
  - `location`: Free-form location string (e.g. "Dallas, TX").
  - `status`: `"posted"`, `"removed"`, etc.
  - `isActive`: Boolean (`true` = active).
  - `datePosted`: Datetime when posted.
  - `validThrough`: Expiration timestamp.
  - `submittedUrl`: Live public URL on client domain.
- **`prod_jobiak_ai.userAnalytics`**:
  - Tracks user and bot traffic on job pages.
  - `employerId`: Client identifier.
  - `childJobId`: References `job.jobId`.
  - `jobPubJobId`: Identifier used in stats queries.
  - `isBot`: Boolean.
  - `isFromGoogle`: Boolean.
  - `browserType`: Browser name (e.g. "Chrome", "Safari", "Unknown").
  - `deviceType`: Device category ("Desktop", "Mobile", "Unknown").
  - `ipAddress`: Visitor IP address.
  - `viewDate` / `createdDt`: View timestamp.
- **`prod_jobiak_ai.jobsGoogleSubmittedLog`**:
  - Google Indexing API submission records.
  - `jobId`: Job identifier.
  - `callType`: `"URL_UPDATED"` (posted/updated) or `"URL_DELETED"` (expired/removed).
  - `createdAt`: Submission timestamp.

### B. Direct Apply & Programmatic Architecture (`directclients_prod` / `{client}_prod`)
- **`Target_P4_Opt`**:
  - `_id`: MongoDB ObjectId.
  - `employerId`: Client identifier (e.g. `emp-jbk-lettuce`).
  - `jobtitle`: Job title.
  - `location`: "City, State" format.
  - `locationKeywords`: List of search keyword strings (supports `{city}` and `{state}` placeholders).
  - `gpost`: Numeric status code:
    - `1`: To Post (ready for Google Indexing)
    - `3`: Posting Queue
    - `4`: Post Fail
    - `5`: Posted (Active on Google)
    - `6`: Expired (Removed from Google)
    - `8`: Expires Queue
  - `job_status`: `3` indicates job was removed from feed (Feed Expired).
  - `gpost_date`: Date when posted (`gpost: 5`).
  - `gpost_expire_date`: Date when expired (`gpost: 6`).
  - `pub_expired`: Anticipated expiration date.
- **`aj_jp_google_logs`**:
  - `callType`: `"URL_UPDATED"` or `"URL_DELETED"`.
  - `status_update`: Execution status (`4` = failure).
  - `createdAt`: Log timestamp.
- **`aj_jp_jobqueue`**:
  - Queue management for pending indexing batches.

### C. Auxiliary Scraping, Cleansing & Audit Databases
- **`ETL_Scrapping_Data.ETL_Scraping_Data`**:
  - Raw scraped jobs from client feeds.
  - `employerId`, `clientJobId`, `job_status` (`3` = expired), `updatetime`.
  - Used to determine **Proxy To_Post**: jobs in `ETL_Scraping_Data` with `job_status != 3` that do NOT exist in `prod_jobiak_ai.job`.
- **`data_cleansing.ETL_AUD_Data`**:
  - Audit table for deleted/removed feed records (`Type == 0`).
  - Used to calculate **Proxy FeedExpiredJobs**.
- **`jobicarenode_prod.Target_P4_Opt`**:
  - JobiCare normalized job feed data. Used in `updates.py` and `feed.py`.
- **`proxy_stats`**:
  - `config`: Contains active proxy export configurations (`EmployerId`, `Status`, `Company`).
  - `run_logs`: Audit log of daily exports and synchronization status.

---

## 4. Bot Detection & Google Organic Search View Logic

### Google Organic Search View Filter (Pure Human Traffic)
To count genuine organic user views from Google for reporting and client analytics, the exact standard filter is:

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
Googlebot crawler visits are queried using:
```python
GOOGLEBOT_FILTER = {
    "employerId": emp_id,
    "isBot": True
}
```

### Unique IP / Click Deduplication
When calculating unique Google visits/clicks per job, group by visitor IP address and Job ID:
```python
clicks_pipeline = [
    {"$match": GOOGLE_VIEW_FILTER},
    {"$group": {"_id": {"ip": "$ipAddress", "job": "$childJobId"}}},
    {"$count": "count"}
]
```

---

## 5. Keywords Management System & Standard Formats

Keywords are stored in two distinct MongoDB schemas depending on whether they are general/title/company keywords or geographic location keywords.

> [!IMPORTANT]
> **Strict Rule for Job Titles:**  
> In all keyword collections, the `title` field must **always be in lower case** (e.g. `cook`, `dietary aide`, `housekeeper`, `laundry worker`, `room attendant - hotels & hospitality`, `floor tech`, `registered dietitian`).

### Format 1: `All Keywords` (General, Title-to-Title, Company Keywords)
Used for `genericKeywords`, `titleToTitle`, and `companyKeywords`.

**Schema (14 Columns):**
`_id, employerId, city, state, confidenceValue, keyword, keywordType, operatorType, title, isActive, createdAt, createdBy, _class, companyName`

**Field Specifications:**
- `_id`: 24-character hexadecimal MongoDB ObjectId.
- `employerId`: Target employer ObjectId (e.g. `6a904f26060e8f0b78b0dc81`).
- `city`: Empty string for non-geographic keywords.
- `state`: Empty string for non-geographic keywords.
- `confidenceValue`: Default `"0d"`.
- `keyword`: The actual keyword string (e.g. `"Prep cook hiring near me"`).
- `keywordType`: One of `genericKeywords`, `titleToTitle`, `companyKeywords`.
- `operatorType`: `"equals-title"`.
- `title`: Lowercase job title (e.g. `"cook"`).
- `isActive`: `"true"` (boolean string).
- `createdAt`: ISO 8601 UTC timestamp (e.g. `"2026-11-12T00:00:00.000Z"`).
- `createdBy`: Author email (e.g. `"tarun.dammu@jobiak.com"`).
- `_class`: `"ai.jobiak.reports.KeywordLocation"`.
- `companyName`: Target company name in quotes (e.g. `"healthcare services group, inc"`).

### Format 2: `Location Keywords` (`locationKeywords`)
Used for dynamic geographic searches with location placeholders.

**Schema (10 Columns):**
`_id, employerId, confidenceValue, keyword, keywordType, operatorType, title, isActive, companyName, createdAt`

**Field Specifications:**
- `keyword`: Contains templates such as:
  - `"{title} jobs in city, state"`
  - `"{title} jobs near city, state"`
  - `"{title} jobs hiring near city, state"`
  - `"{title} jobs near me city, state"`
- `keywordType`: Always `"locationKeywords"`.
- `title`: Lowercase job title.

### Dynamic Location Keyword Expansion in Database
For Direct Apply domains like Lettuce (`emp-jbk-lettuce`), jobs in `Target_P4_Opt` store template keywords like:
`"Prep Cook jobs in {city}, {state}"`
The script `update_lettuce_keywords_in_db.py` parses the job's `location` field (e.g. `"Chicago, IL"`), extracts `city` and `state`, replaces the placeholders, and bulk-updates `locationKeywords` in MongoDB.

---

## 6. Daily Operations & Metric Calculation Rules

### Core Metrics in `Stats/dailystats.py`

| Metric | Source Collection | Logic | Output Doc |
|---|---|---|---|
| **To_Post (Proxy)** | `ETL_Scraping_Data` vs `job` | `feed_ids - handled_ids` (clientJobIds in feed not yet in job collection) | `TODAY` |
| **To_Post (Direct)** | `Target_P4_Opt` | `gpost == 1 && job_status != 3` | `TODAY` |
| **FeedExpiredJobs (Proxy)** | `data_cleansing.ETL_AUD_Data` | Docs with `company == company_name` and `Type == 0` | `TODAY` |
| **FeedExpiredJobs (Direct)**| `Target_P4_Opt` | `job_status == 3` | `TODAY` |
| **Posted_Jobs** | `job` / `Target_P4_Opt` | `action == 'post'`, `gpost == 5`, within yesterday's 24h window | `YESTERDAY` |
| **Updated_Jobs** | `job` / `Target_P4_Opt` | `action == 'update'`, `gpost == 5`, within yesterday's window | `YESTERDAY` |
| **Cache_Updated_Jobs** | Computed | `(Posted + Updated + Reposts) - Google_URL_UPDATED` | `YESTERDAY` |
| **DB_Clicks** | `userAnalytics` | Organic Google views grouped by `(ipAddress, jobId)` within window | `YESTERDAY` |
| **Bot_Visits** | `userAnalytics` | `isBot == True` within yesterday's window | `YESTERDAY` |

---

## 7. Operational Scripts Inventory

### Root Scripts (`./`)
- `generate_client_views_excel.py`: Multi-tab formatted Excel views & bot report generator for YES! Communities and QRM.
- `generate_hcsg_views_excel.py`: Detailed 7-tab Excel analytics workbook for Healthcare Services Group (HCSG).
- `generate_lettuce_keywords.py`: Generates CSV of Lettuce jobs with resolved city/state location keywords.
- `update_lettuce_keywords_in_db.py`: Executes bulk `$set` operations in `directclients_prod.Target_P4_Opt` to replace `{city}`/`{state}` placeholders.
- `hcsg.py`: Live HCSG views and bot analytics sync to Google Sheets (`1c3WqKgewVn0mqQTsH4pQzuR8P9JK6xI5QJ2aXLsekQk`).
- `postings.py`: Validates feed jobs against JobiCare and scraping DB, syncs to Google Sheets "Postings".
- `updates.py`: Validates posted active jobs, cross-references JobiCare and analytics, exports updates.
- `feed.py`: Multi-client feed reconciliation tool comparing JobiCare (`jobicarenode_prod`) vs Production (`prod_jobiak_ai`).
- `issue.py`: HCSG Google Job views audit analyzing performance before and after specific system events.

### Subdirectories
- **`Proxy/`**:
  - `updates_postings.py`: Automated daily export of Postings (diff between scraped feed and production) and Updates (expiring active jobs), emailed via SMTP.
  - `proxy_api.py`: FastAPI endpoints for proxy metrics.
  - `earnhaus_export_api.py`: EarnHaus job export API.
- **`Stats/`**:
  - `dailystats.py`: Daily automated pipeline recording snapshot and closed-window metrics into `daily_stats.output`.
  - `dailystats_old.py`: Historical cumulative backfill engine.
  - `clicks_report.py`: IP grouping and click analysis.
  - `stats_email.py`: Daily HTML email digest of organic search clicks.
  - `semrush_urls.py`: Audits indexed URLs against Semrush whitelist.
- **`Revenue/`**:
  - `banana.py`: Unique IP clicks reporting into MongoDB and Google Sheets.
  - `whatjobs.py` & `jobget.py`: Revenue reconciliation with publisher partner sheets.
  - `creds.py`: Healthcheck and connection testing across all URIs in `mongo_creds.creds`.

---

## 8. Anti-Clutter Standard: Creating New Scripts

To prevent workspace clutter, all newly developed scripts should be placed directly inside the `antigravity/` folder.

### Using the Central Connection Helper (`antigravity/db_helper.py`)
Import `get_database_by_name` and `get_collections_for_domain` to connect to any database:

```python
from antigravity.db_helper import get_database_by_name, get_collections_for_domain

# 1. Connect to Direct Apply (Lettuce, etc.)
dc_db = get_database_by_name("directclients_prod")
col = dc_db["Target_P4_Opt"]

# 2. Connect to Proxy (HCSG, Concentrix, etc.)
prod_db = get_database_by_name("prod_jobiak_ai")
jobs_col = prod_db["job"]
analytics_col = prod_db["userAnalytics"]

# 3. Connect to Scraping or Cleansing
etl_db = get_database_by_name("ETL_Scrapping_Data")
cleansing_db = get_database_by_name("data_cleansing")
```
