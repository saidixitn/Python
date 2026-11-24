import os
import re

file_path = r"c:\Users\JOBIAK\Documents\Python\GEMINI.md"

with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

# Let's locate Section 12
s12_start = text.find("## 12. Root Workspace Client Analytics")
s13_start = text.find("## 13. Real-Time Telegram Alerts")

if s12_start == -1 or s13_start == -1:
    print("Error: Could not locate Section 12 or Section 13 boundaries!")
    exit(1)

new_section_12 = """## 12. Root Workspace Client Analytics: HCSG, Lettuce, ABS Kids, QRM, YES Communities, Day-1 Reports & XML Comparison

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
  $$\\text{MoM \\% Change} = \\frac{\\text{Current Month Views} - \\text{Prior Month Views}}{\\text{Prior Month Views}} \\times 100$$
- **Data Quality Audit**: Scans for duplicate `uniqueId` or `clientJobId` values in production and writes an automated alert tab in the Google Spreadsheet.

#### 3. Before vs. After Event Attribution (`issue.py`)
When traffic drops or feed ingestion changes on an exact date (`ISSUE_DATE`, e.g. `2026-10-24`), `issue.py` partitions the catalog and analytics into two distinct time windows:
- **Metrics Evaluated Before vs After**:
  1. Active Posted Jobs vs Expired Jobs count.
  2. Distinct locations with active listings vs distinct locations generating views.
  3. Location View Penetration: $\\frac{\\text{Locations with Views}}{\\text{Total Active Locations}}$.
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
  $$\\Delta \\text{Views} = \\text{Views}_{\\text{Date 2}} - \\text{Views}_{\\text{Date 1}}$$
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
  $$\\text{Total Daily Views} = \\text{Views}(\\text{userAnalytics}) + \\text{Views}(\\text{userAnalytics\\_prod})$$
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
"""

# Replace Section 12 with the new expanded, self-contained section
new_content = text[:s12_start] + new_section_12.strip() + "\n\n" + text[s13_start:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"Updated GEMINI.md successfully. New size: {len(new_content)} characters.")
