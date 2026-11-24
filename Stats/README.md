# Stats & Analytics Subsystem

Comprehensive architectural guide, operational manual, and data dictionary for the Jobiak Stats pipeline, including `dailystats.py` (Daily Operations) and `dailystats_old.py` (Historical Backfill Engine).

---

## Table of Contents
1. [Architectural Overview](#architectural-overview)
2. [Multi-Tenant MongoDB Architecture & URI Management](#multi-tenant-mongodb-architecture--uri-management)
3. [Domain Types & Processing Strategies](#domain-types--processing-strategies)
4. [Script 1: `dailystats.py` (Live Daily Operations)](#script-1-dailystatspy-live-daily-operations)
5. [Script 2: `dailystats_old.py` (Historical Backfill Engine)](#script-2-dailystats_oldpy-historical-backfill-engine)
6. [Database, Collection & Field Dictionary](#database-collection--field-dictionary)
7. [Other Stats Scripts in this Directory](#other-stats-scripts-in-this-directory)
8. [Setup, Execution & Verification](#setup-execution--verification)

---

## Architectural Overview

The statistics pipeline tracks job posting activity, Google Indexing API calls, cache synchronizations, bot visits, and organic Google search clicks across diverse employer domains.

```mermaid
flowchart TD
    subgraph Config ["Configuration Layer"]
        ENV[".env (MONGO_URI)"] --> LocalClient["Root MongoClient"]
        LocalClient --> InputCol["daily_stats.input"]
        LocalClient --> CredsCol["mongo_creds.creds"]
    end

    subgraph DynamicRouter ["Dynamic Connection Router (get_database_by_name)"]
        CredsCol --> CacheLock["Thread-Safe CACHE_LOCK"]
        CacheLock --> DBCache["In-Memory DB_CACHE & CLIENT_CACHE"]
    end

    subgraph Clusters ["Database Clusters"]
        DBCache --> ProxyDB["prod_jobiak_ai (Proxy)"]
        DBCache --> DCDB["directclients_prod (Direct Apply)"]
        DBCache --> ProgDB["{client}_prod (Programmatic)"]
        DBCache --> CleansingDB["data_cleansing"]
        DBCache --> ScrapingDB["ETL_Scrapping_Data"]
    end

    subgraph ProcessingPipelines ["Processing Pipelines"]
        ProxyDB & DCDB & ProgDB --> DailyStats["dailystats.py (Daily Operational Snapshot)"]
        ProxyDB & DCDB & ProgDB --> DailyStatsOld["dailystats_old.py (Historical Cumulative Backfill)"]
    end

    subgraph OutputCollections ["Storage Layer"]
        DailyStats --> OutputCol["daily_stats.output (TODAY + YESTERDAY docs)"]
        DailyStatsOld --> OldStatsCol["daily_stats.oldstats (97 Dates per Domain)"]
    end
```

---

## Multi-Tenant MongoDB Architecture & URI Management

Rather than hardcoding database connection strings, the application uses a **dynamic multi-tenant credential registry**:

1. **Bootstrap Connection**:
   - The root connection string is loaded from `.env` via `os.getenv("MONGO_URI")`.
   - Connects to the local/central MongoDB cluster hosting `daily_stats` and `mongo_creds`.

2. **Dynamic Credential Resolution (`mongo_creds.creds`)**:
   - Each remote employer cluster or external service has a record in `mongo_creds.creds`:
     ```json
     {
       "domain": "directclients_prod",
       "mongo_uri": "mongodb://user:pass@cluster-host:27017/directclients_prod?authSource=admin..."
     }
     ```
   - When a script accesses a database name (e.g. `directclients_prod`, `prod_jobiak_ai`, `data_cleansing`, `ETL_Scrapping_Data`, `hextill_prod`), it calls:
     ```python
     def get_database_by_name(db_name):
     ```
   - This function:
     - Checks if `db_name` already exists in `DB_CACHE`.
     - If not, acquires `CACHE_LOCK` (thread-safe), queries `mongo_creds.creds` for `mongo_uri`.
     - Initializes a new `MongoClient` with `maxPoolSize=100`.
     - Stores the instance in `CLIENT_CACHE` and database handle in `DB_CACHE`.

---

## Domain Types & Processing Strategies

Domains in `daily_stats.input` are categorized into three distinct domain types:

| Domain Type | Primary Database | Jobs Collection | Google Indexing Logs | Employer ID Filter |
|---|---|---|---|---|
| **Proxy** | `prod_jobiak_ai` | `job` | `jobsGoogleSubmittedLog` | `{"employerId": {"$in": employer_ids}}` |
| **Direct Apply** | `directclients_prod` | `Target_P4_Opt` | `aj_jp_google_logs` | `{"employerId": {"$in": employer_ids}}` |
| **Programmatic** | `{client}_prod` (e.g. `hextill_prod`) | `{client}_Target_P4_Opt` | `aj_jp_google_logs` | `{}` (Tenant database is dedicated to this client) |

### Auxiliary Databases (Used by Proxy Domains)
- **`data_cleansing.ETL_AUD_Data`**: Audit table storing jobs removed from feeds (`Type == 0`), used to calculate `FeedExpiredJobs`.
- **`ETL_Scrapping_Data.ETL_Scraping_Data`**: Raw feed collection storing scraped jobs. Used alongside `prod_jobiak_ai.job` to calculate `To_Post`.

---

## Script 1: `dailystats.py` (Live Daily Operations)

### Purpose
Scheduled to run daily via PM2 or cron. On every execution, it generates **two documents per domain** in `daily_stats.output`:
1. **`TODAY` Document (`Date: today 00:00:00 UTC`)**:
   - Represents a live, rolling snapshot of the current state of pending work.
   - Stores only `To_Post` and `FeedExpiredJobs` (overwritten on each daily run).
2. **`YESTERDAY` Document (`Date: yesterday 00:00:00 UTC`)**:
   - Represents the complete, finalized 24-hour window from `00:00:00` to `23:59:59` UTC of yesterday.
   - Preserves historical posting and performance metrics.

### Key Calculation Formulas & Logic

1. **`Posted_Bot` with Cache-Updated Exclusion**:
   - Jobs that were already fresh in cache do not consume a Google bot call.
   - **Formula**:
     $$\text{Posted\_Bot} = \max(\text{Posted\_Jobs} - \text{Cache\_Updated\_Jobs}, 0)$$
2. **`Cache_Updated_Jobs`**:
   - Quantifies jobs processed locally where Google did not receive a new `URL_UPDATED` call because the content hash had not changed.
   - **Formula**:
     $$\text{Cache\_Updated\_Jobs} = \max((\text{Posted\_Jobs} + \text{Updated\_Jobs} + \text{Reposts}) - \text{Google\_URL\_Updated}, 0)$$
3. **`DB_Clicks`**:
   - Aggregated from `userAnalytics` within the day window:
     - `isBot: False`
     - `isFromGoogle: True`
     - `browserType != "Unknown"`, `deviceType != "Unknown"`
     - Grouped by `{"ip": "$ipAddress", "job": "$jobId"}` to ensure unique IP + Job clicks.
4. **`Bot_Visits`**:
   - Count of documents in `userAnalytics` where `isBot: True` within the date window.
5. **`To_Expire_In_5Days`**:
   - Active jobs whose `validThrough` timestamp falls within the upcoming 5 days:
     `{"status": "posted", "isActive": True, "validThrough": {"$lt": now + 5 days}}`.

---

## Script 2: `dailystats_old.py` (Historical Backfill Engine)

### Purpose
Created to accurately backfill historical statistics across a closed date window (e.g., **`2026-08-01` to `2026-11-05`**, 97 daily data points) into the designated target collection `daily_stats.oldstats`.

### Critical Differences from `dailystats.py`

1. **Excluded Live Metrics**:
   - `To_Post` and `FeedExpiredJobs` cannot be computed retroactively because external scrape feeds and audit queues only hold recent/current states.
   - `To_Expire_In_5Days` is omitted per user requirements.
2. **True Cumulative Monotonic Totals**:
   - `Total_Posted_Jobs` and `Total_Expired_Jobs` reflect the **exact cumulative count of all jobs posted or expired from inception up to each specific date's `WindowEnd`**:
     $$\text{Total\_Posted\_Jobs}(D) = \text{Initial}_{<\text{START}} + \sum_{d = \text{START}}^{D} \text{Posted\_Bot}(d)$$
     $$\text{Total\_Expired\_Jobs}(D) = \text{Initial}_{<\text{START}} + \sum_{d = \text{START}}^{D} \text{Expires\_Bot}(d)$$
   - Verified to be strictly non-decreasing across all dates.
3. **Log-Based Source of Truth**:
   - In production, live job collections (`job`, `Target_P4_Opt`) overwrite `gpost_date`, `datePosted`, and `updatedAt` when a job is re-scraped or re-indexed.
   - Therefore, historical daily posted and expired events are derived from append-only audit logs:
     - Proxy: `prod_jobiak_ai.jobsGoogleSubmittedLog`
     - Direct Apply / Programmatic: `aj_jp_google_logs`
4. **High-Performance Batch Date-Grouped Analytics**:
   - Querying `userAnalytics` individually for 97 dates per domain caused socket resets (`WinError 10053`) due to heavy unindexed scans on remote clusters.
   - `dailystats_old.py` aggregates `Bot_Visits` and `DB_Clicks` in **one batch aggregation per employer** across the entire 3-month window, partitioning the results in memory.
5. **Parallel Worker Pool with Concurrency Throttling**:
   - Utilizes `concurrent.futures.ThreadPoolExecutor(max_workers=3)` to process domains concurrently without exhausting MongoDB connection pools.
6. **Automatic Indexing**:
   - Automatically builds a compound index on the target collection:
     `oldstats.create_index([("Domain", 1), ("Date", 1)], unique=True)`

---

## Database, Collection & Field Dictionary

### 1. `daily_stats.output` & `daily_stats.oldstats` (Result Documents)

| Field Name | Type | Description & Significance | Present in `dailystats.py` | Present in `dailystats_old.py` |
|---|---|---|:---:|:---:|
| `Domain` | String | Domain name identifier (e.g. `abskids.com/gfj/`) | Yes | Yes |
| `DomainType` | String | Classification: `Proxy`, `Direct Apply`, or `Programmatic` | Yes | Yes |
| `Company` | String | Resolved human-readable employer name | Yes | Yes |
| `employerId` | String / Array | Identifier(s) matching client records in jobs/logs | Yes | Yes |
| `Date` | Date (UTC) | Start of the measurement day (`YYYY-MM-DD 00:00:00 UTC`) | Yes | Yes |
| `WindowStart` | Date (UTC) | Exact start of the 24-hour evaluation window | Yes | Yes |
| `WindowEnd` | Date (UTC) | Exact end of the 24-hour evaluation window | Yes | Yes |
| `GeneratedAt` | Date (UTC) | Timestamp when the document was computed and written | Yes | Yes |
| `To_Post` | Integer | Live feed jobs waiting to be posted to Google | Yes (Today doc only) | Excluded |
| `FeedExpiredJobs` | Integer | Live feed jobs flagged as expired | Yes (Today doc only) | Excluded |
| `To_Expire_In_5Days` | Integer | Live jobs expiring within 5 days | Yes | Excluded |
| `Total_Posted_Jobs` | Integer | Cumulative total jobs posted up to `WindowEnd` | Yes | Yes (Strictly Cumulative) |
| `Total_Expired_Jobs` | Integer | Cumulative total jobs expired up to `WindowEnd` | Yes | Yes (Strictly Cumulative) |
| `Posted_Jobs` | Integer | Jobs submitted with action `post` in the day window | Yes | Yes |
| `Updated_Jobs` | Integer | Jobs submitted with action `update` in the day window | Yes | Yes |
| `Reposts` | Integer | Jobs submitted with action `repost` in the day window | Yes | Yes |
| `Expired_Jobs` | Integer | Jobs submitted with action `expire` in the day window | Yes | Yes |
| `Posted_Bot` | Integer | New Google URL updates excluding cache updates | Yes | Yes |
| `Expires_Bot` | Integer | Deletion calls sent to Google Indexing API (`URL_DELETED`) | Yes | Yes |
| `Cache_Updated_Jobs` | Integer | Jobs refreshed without calling Google Indexing API | Yes | Yes |
| `Live_In_Google` | Integer | Jobs confirmed active and indexed in Google | Programmatic/DA only | Programmatic/DA only |
| `Live_In_Bot` | Integer | Jobs queued/active in bot indexer | Programmatic/DA only | Programmatic/DA only |
| `Updated_Bot` | Integer | URL updates confirmed by Google bot | Programmatic/DA only | Programmatic/DA only |
| `Expired_Bot` | Integer | Deletions confirmed by Google bot | Programmatic/DA only | Programmatic/DA only |
| `DB_Clicks` | Integer | Unique (IP + Job) organic user clicks from Google | Yes | Yes |
| `Bot_Visits` | Integer | Bot/crawler visits recorded on job pages | Yes | Yes |

---

### 2. Upstream Operational Collections

#### `daily_stats.input`
- **Purpose**: Defines which domains are tracked.
- **Fields**:
  - `Domain` (String): e.g. `"championwindow.com/gfj"`
  - `DomainType` (String): `"Proxy"`, `"Direct Apply"`, or `"Programmatic"`
  - `employerId` (String or List[String]): e.g. `"6aa8d214060e8f0b78b0dc87"` or `["emp-jbk-apexfocusgroup", "emp-jbk-apexfocusgroup_uk"]`
  - `Company` (String, optional): Company name override.

#### `mongo_creds.creds`
- **Purpose**: Maps database/cluster names to authorized connection strings.
- **Fields**:
  - `domain` (String): Database identifier (e.g. `"prod_jobiak_ai"`, `"directclients_prod"`, `"data_cleansing"`)
  - `mongo_uri` (String): MongoDB URI with credentials, hosts, ports, replica sets, and authSource.

#### `prod_jobiak_ai.job` (Proxy Jobs)
- **Fields**:
  - `employerId` (String): Identifier of employer.
  - `status` (String): `"posted"`, `"removed"`.
  - `gpost` (Integer): `1` (to post), `3` (in posting queue), `5` (posted/updated), `8` (in expiry queue).
  - `job_status` (Integer): `3` indicates deleted/inactive.
  - `validThrough` (Date): Expiry datetime.
  - `datePosted` (Date): Timestamp when the job was posted.
  - `clientJobId` (String): Primary external job identifier from the employer's feed.

#### `jobsGoogleSubmittedLog` & `aj_jp_google_logs` (Google Indexing Logs)
- **Fields**:
  - `callType` (String): `"URL_UPDATED"` or `"URL_DELETED"`.
  - `createdAt` (Date): UTC timestamp of the submission to Google.
  - `employerId` / `employer_name` (String): Employer identifier.
  - `jobId` (String/ObjectId): Associated job document ID.
  - `submittedUrl` (String): Canonical URL submitted to Google Indexing API.

#### `userAnalytics` (Traffic & Engagement)
- **Fields**:
  - `employerId` / `employer` (String): Target employer.
  - `isBot` (Boolean): `True` for crawlers/spiders, `False` for human traffic.
  - `isFromGoogle` (Boolean): `True` if referrer originated from Google search.
  - `browserType` (String): Client browser (`"Unknown"`, `"Chrome"`, `"Safari"`, etc.).
  - `deviceType` (String): Client device (`"Mobile"`, `"Desktop"`, `"Tablet"`, `"Unknown"`).
  - `createdDt` (Date or String): Timestamp or `"YYYY-MM-DD"` date string of the event.
  - `ipAddress` (String): Client IP used for deduplication.
  - `jobPubJobId` / `jobId` (String): ID of the clicked job.

---

## Other Stats Scripts in this Directory

| Script | Purpose |
|---|---|
| [`Stats/clicks_report.py`](file:///c:/Users/JOBIAK/Documents/Python/Stats/clicks_report.py) | Analyzes unique clicks, IP groupings, and bot vs. human distribution across employers. |
| [`Stats/stats_email.py`](file:///c:/Users/JOBIAK/Documents/Python/Stats/stats_email.py) | Formats daily statistics into an HTML summary email and dispatches it to stakeholders. |
| [`Stats/to_post.py`](file:///c:/Users/JOBIAK/Documents/Python/Stats/to_post.py) | Identifies newly scraped jobs that need to be published to Google, syncing them with Google Sheets. |
| [`Stats/expires.py`](file:///c:/Users/JOBIAK/Documents/Python/Stats/expires.py) / [`Stats/dc_expires.py`](file:///c:/Users/JOBIAK/Documents/Python/Stats/dc_expires.py) | Scans for jobs with zero engagement or past validity dates and submits deletion queues. |
| [`Stats/semrush_urls.py`](file:///c:/Users/JOBIAK/Documents/Python/Stats/semrush_urls.py) | Audits SEMrush URL whitelists against active indexed URLs. |

---

## Setup, Execution & Verification

### Running Daily Stats (Operational)
```bash
python Stats/dailystats.py
```
- Reads from `daily_stats.input`.
- Inserts/updates `daily_stats.output` with TODAY snapshot and YESTERDAY finalized metrics.

### Running Historical Backfill
```bash
python Stats/dailystats_old.py
```
- Backfills date range `2026-08-01` to `2026-11-05` (97 dates).
- Populates collection `daily_stats.oldstats`.

### Verification Query
To verify document counts and cumulative integrity in MongoDB:
```python
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"))
c = client["daily_stats"]["oldstats"]

print("Total documents:", c.count_documents({}))
print("Total domains  :", len(c.distinct("Domain")))

# Check for absence of excluded fields
for forbidden in ["To_Post", "FeedExpiredJobs", "To_Expire_In_5Days"]:
    assert c.count_documents({forbidden: {"$exists": True}}) == 0, f"Found {forbidden}!"
print("Verification complete: Old stats clean and compliant.")
```
