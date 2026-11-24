import os
import re

file_path = r"c:\Users\JOBIAK\Documents\Python\GEMINI.md"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update Table of Contents
old_toc_10 = "10. [Zero-Click Expiration, Feed Reconciliation (`expires.py`), Updates (`updates.py`) & `jobicarenode_prod`](#10-zero-click-expiration-feed-reconciliation-expirespy-updatespy--jobicarenode_prod)"
new_toc_10 = "10. [Zero-Click Expiration, Feed Reconciliation (`expires.py`), Updates (`updates.py`) & `jobicarenode_prod` Ingestion Collision Check](#10-zero-click-expiration-feed-reconciliation-expirespy-updatespy--jobicarenode_prod-ingestion-collision-check)"

old_toc_12 = "12. [Root Workspace Client Analytics: HCSG, Lettuce Subdomain, ABS Kids, Day-1 Reports & XML Comparison](#12-root-workspace-client-analytics-hcsg-lettuce-subdomain-abs-kids-day-1-reports--xml-comparison)"
new_toc_12 = "12. [Root Workspace Client Analytics: HCSG, Lettuce, ABS Kids, QRM, YES Communities, Day-1 Reports & XML Comparison](#12-root-workspace-client-analytics-hcsg-lettuce-abs-kids-qrm-yes-communities-day-1-reports--xml-comparison)"

old_toc_16 = "16. [GenAI FAQ Engine (`proxy_faq.py`), Keywords Schemas & HTML Cleaners](#16-genai-faq-engine-proxy_faqpy-keywords-schemas--html-cleaners)"
new_toc_16 = "16. [GenAI FAQ Engine, Keywords Schemas, ATS Description Quality & Scrape Cleaners](#16-genai-faq-engine-keywords-schemas-ats-description-quality--scrape-cleaners)"

content = content.replace(old_toc_10, new_toc_10)
content = content.replace(old_toc_12, new_toc_12)
content = content.replace(old_toc_16, new_toc_16)

# 2. Update Section 10: Add Subsection D
sec10_marker = "## 10. Zero-Click Expiration, Feed Reconciliation (`expires.py`), Updates (`updates.py`) & `jobicarenode_prod`"
sec10_replacement_header = "## 10. Zero-Click Expiration, Feed Reconciliation (`expires.py`), Updates (`updates.py`) & `jobicarenode_prod` Ingestion Collision Check"

sec10_addition = """

### D. Cross-System Feed Staging Reconciliation & Pre-Posting Collision Detection (`jobicarenode_prod` vs `prod_jobiak_ai.job`)
- **What & Why**: When preparing to publish new jobs from Jobicare staging (`jobicarenode_prod.Target_P4_Opt`) to Proxy Production (`prod_jobiak_ai.job`), we must check whether candidate jobs (`gpost in [1, 3]`, `job_status != 3`) already exist in `prod_jobiak_ai.job`.
- **The Core Rule**: **"If these uniqueKeys are already present in `prod_jobiak_ai.job`, WE CANNOT POST!"** Posting them would generate duplicate URLs, confuse Google for Jobs indexing, or resurrect removed/expired listings without fresh ATS data.
- **The Key Mapping**:
  $$\\text{jobicarenode\\_prod.Target\\_P4\\_Opt.uniqueKey} \\longleftrightarrow \\text{prod\\_jobiak\\_ai.job.clientJobId}$$
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
"""

content = content.replace(sec10_marker, sec10_replacement_header)

# Insert sec10_addition right before "## 11. Duplicate Detection"
idx_sec11 = content.find("## 11. Duplicate Detection")
if idx_sec11 != -1:
    content = content[:idx_sec11] + sec10_addition.strip() + "\n\n---\n\n" + content[idx_sec11:]

# 3. Update Section 12: Add QRM, ABS Kids, YES Communities, and Indianapolis analysis
sec12_marker = "## 12. Root Workspace Client Analytics: HCSG, Lettuce Subdomain, ABS Kids, Day-1 Reports & XML Comparison"
sec12_replacement_header = "## 12. Root Workspace Client Analytics: HCSG, Lettuce, ABS Kids, QRM, YES Communities, Day-1 Reports & XML Comparison"

sec12_addition = """

### C. Enterprise Client 9-Tab Clicks Performance Reports (QRM & ABS Kids)
- **What & Why**: Full lifecycle reporting engine generating standardized 9-tab Excel workbooks (`QRM_Clicks_Performance_Report.xlsx`, `ABS_Kids_Clicks_Performance_Report.xlsx`) breaking down traffic velocity, title/location performance, daily trajectories, visitor locations, and inventory health.
- **The 9 Standard Report Tabs**:
  1. `Executive Overview`: KPI summary cards (Total Google Clicks, Active Jobs, Expired Jobs, Unique Clicked Jobs, Unique Visitor IPs, Mobile vs Desktop %).
  2. `Title_Location_Detailed`: Granular matrix of every job title + location combination with active/expired counts, clicks, mobile/desktop split, and first/last click dates.
  3. `Title_Wise_Performance`: Aggregated title-level rollups with zero-click job counts, performing job counts, and click concentration.
  4. `Location_Wise_Breakup`: State- and city-level clicks, unique visitor IPs, and active inventory distribution.
  5. `Daily_Clicks_Breakup`: Day-by-day click volume, unique IPs, mobile/desktop breakdown, and distinct titles/locations clicked.
  6. `Title_Daywise_Breakup`: Pivot-style daily trend for every job title across the entire analysis window.
  7. `Visitor_Location_Breakup`: Geographic origin of applicants (`city`, `region`, `country`) with device breakdown.
  8. `Device_and_Browser_Breakdown`: Device types (Mobile/Desktop/Tablet) and browser families (Chrome, Safari, Edge, Firefox).
  9. `Inventory_Status_Audit`: Full catalog audit (`status == 'posted'` & `isActive == True` vs `status == 'removed'`).
- **CRITICAL Performance Rule**: When querying `prod_jobiak_ai.userAnalytics` for Proxy clients, **ALWAYS append `.hint('employerId_1')`**!
  ```python
  # CORRECT - finishes in 0.8s:
  cursor = db.userAnalytics.find(
      {'employerId': emp_id, 'isFromGoogle': True, 'isBot': False},
      {'jobId': 1, 'createdDt': 1, 'ipAddress': 1, 'city': 1, 'region': 1, 'deviceType': 1, '_id': 0}
  ).hint('employerId_1')

  # WRONG - causes full scan of 15M+ records, times out after 60s:
  cursor = db.userAnalytics.find({'employerId': emp_id, 'isFromGoogle': True, 'isBot': False})
  ```

### D. YES Communities Peak Day vs. Yesterday Performance & Expiry Attribution Engine
- **Target Client**: YES Communities (`employerId: "6a86c3d7060e8f0b78b0dc66"` in `prod_jobiak_ai.job`).
- **Core Numbers**:
  - Total Jobs: 1,295 (884 Active Posted, 409 Expired/Removed).
  - All-Time Peak Day: **`2026-10-05` (49 clicks)** across 46 unique jobs.
  - Target October Max Day: **`2026-10-19` (48 clicks)** across 41 unique jobs.
  - Recent Velocity: `2026-11-16` (15 clicks), `2026-11-17` (16 clicks).
- **The Expiry Attribution Problem**: When clicks drop from peak (48 &rarr; 15/16), clients ask: *"Did we expire the performing jobs, or are the jobs still active?"*
- **Attribution Methodology**:
  1. Extract all jobs clicked on the peak day (`2026-10-19`).
  2. Cross-reference their current state in `prod_jobiak_ai.job`:
     - **Expired Listings (18.8% of drop / 9 clicks)**: 6 specific jobs reached their `validThrough` date between Nov 1 and Nov 7, 2026, and were naturally expired (`status: "removed", isActive: False`). Example: *Office Administrator* in Dearborn, MI drove 4 clicks on 10-19 and expired Nov 7.
     - **Active Listings Experiencing Rank Decline (81.2% of drop / 38 clicks)**: 35 jobs that generated 39 clicks on 10-19 are **STILL ACTIVE AND POSTED** today, capturing 1 click yesterday due to organic Google for Jobs impression shifts.
     - **New Active Gainers (+14 to +15 clicks)**: New active listings (e.g. *Office Administrator* in Corpus Christi, Fishers, Utica) captured traffic yesterday.
- **Single-CSV Breakdown Architecture (`generate_single_csv_breakdown.py`)**:
  Combines all 105 jobs clicked on peak or yesterday into one master CSV (`YES_Communities_Max_Day_vs_Yesterday_Job_Clicks_Breakdown.csv`) featuring:
  `Job ID`, `Title`, `Location`, `Current Status`, `Active Status`, `Is Job Expired?`, `Date Posted`, `Valid Through`, `Clicks (Max Day 10-19)`, `Clicks (Peak 10-05)`, `Clicks (Yesterday 11-17)`, `Clicks (Prior Day 11-16)`, `Clicks Change`, `Performance Impact Category`, `Lifetime Clicks`, `Job URL`.

### E. Multi-Perspective Geographic Clicks Analysis (Indianapolis, IN Case Study)
When auditing clicks for a specific city or metro market (e.g. `Indianapolis, IN, US`), analysts must distinguish between **two distinct perspectives**:
1. **Perspective A — Clicks on Job Postings located in that City (`job.location == "Indianapolis,IN,US"`)**:
   - 5 total jobs posted for YES Communities in Indianapolis, IN.
   - **14 total lifetime Google clicks** across 10 active dates (85.7% captured by *Office Administrator* `6ab0f04420604203cdb1143b`).
2. **Perspective B — Clicks from Job Seekers / Visitors located in that City (`userAnalytics.city == "Indianapolis"`)**:
   - Job seekers located in Indianapolis generated **148 total Google clicks** across YES Communities listings.
   - These users clicked on Indianapolis jobs (10 clicks) as well as adjacent Indianapolis metropolitan suburbs (138 clicks): Greenwood IN, Avon IN, Greenfield IN, Fishers IN, Beech Grove IN, Plainfield IN, Anderson IN, Zionsville IN, Cicero IN.
3. **Perspective C — Intersection (Indianapolis Job AND Indianapolis Visitor)**:
   - Exactly **10 clicks** where both the job posting and the applicant resided in Indianapolis.
"""

content = content.replace(sec12_marker, sec12_replacement_header)

idx_sec13 = content.find("## 13. Real-Time Telegram Alerts")
if idx_sec13 != -1:
    content = content[:idx_sec13] + sec12_addition.strip() + "\n\n---\n\n" + content[idx_sec13:]

# 4. Update Section 16: Add Subsection D (Job Description Quality)
sec16_marker = "## 16. GenAI FAQ Engine (`proxy_faq.py`), Keywords Schemas, Scrapers & HTML Cleaners"
sec16_replacement_header = "## 16. GenAI FAQ Engine, Keywords Schemas, ATS Description Quality & Scrape Cleaners"

sec16_addition = """

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
"""

content = content.replace(sec16_marker, sec16_replacement_header)

idx_sec17 = content.find("## 17. Production VPS PM2 Ecosystem")
if idx_sec17 != -1:
    content = content[:idx_sec17] + sec16_addition.strip() + "\n\n---\n\n" + content[idx_sec17:]

# 5. Update Section 18: Add new Dictionary terms
dict_addition = """
- **`Apply Leak`**: Outbound career URLs or applicant warnings inside job descriptions instructing candidates to bypass Jobiak proxy tracking (`/gfj/`) and visit client root career pages directly.
- **`Pre-Posting Collision Check`**: Querying `prod_jobiak_ai.job` (`clientJobId`) with candidate `uniqueKey`s from `jobicarenode_prod.Target_P4_Opt` to block duplicate or conflicting listings before ingestion.
- **`Scrape Timestamp`**: Plain-text date/time string prepended by scrapers at the start of a description (`"Posted Wednesday, September 2, 2026, 4:00 AM"`), corrupting Google for Jobs snippets.
- **`Trailing Address (Description)`**: Physical street address floating outside HTML tags after the closing `</p>` tag.
- **`validThrough`**: ISO datetime field in `prod_jobiak_ai.job` establishing the schema expiration cutoff; jobs passing this date transition to `status: "removed", isActive: False`.
"""

idx_sec19 = content.find("## 19. How to Ask & Standard Execution Playbook")
if idx_sec19 != -1:
    content = content[:idx_sec19] + dict_addition.strip() + "\n\n---\n\n" + content[idx_sec19:]

# 6. Update Section 19: Add new Playbook rows
playbook_addition = """| **"Check if jobs in jobicare are already in prod_jobiak_ai (cannot post)"** | 1. Query `jobicarenode_prod.Target_P4_Opt` for candidate uniqueKeys (`employerId: emp-jicn-{client}`, `job_status != 3`, `gpost in [1, 3]`).<br/>2. Query `prod_jobiak_ai.job` for employer's existing `clientJobId`s.<br/>3. Match `uniqueKey == clientJobId`: records present are flagged **CANNOT POST** (break down by `posted`/`removed`/`processing`); records absent are flagged **AVAILABLE TO POST**.<br/>4. Output both CSV and `.txt` lists to `antigravity/`. |
| **"Compare Max Clicks Date vs Yesterday with job-level expiry attribution"** | 1. Fetch all Google clicks from `userAnalytics` using `.hint('employerId_1')` and identify all-time peak day and yesterday.<br/>2. Extract every job clicked on either date.<br/>3. Reconcile with `prod_jobiak_ai.job`: attribute drops between natural job expirations (`validThrough` elapsed -> `status: removed`) vs organic rank decline on active jobs (`status: posted`).<br/>4. Output multi-tab Excel + single master breakdown CSV to `antigravity/`. |
| **"Audit job descriptions for ATS scrape timestamps, rogue dots, and apply leaks"** | 1. Scan `description` across all active jobs (`status: "posted"`).<br/>2. Check leading text before first `<` for `^Posted [Day], [Date], [Time]` regex matches.<br/>3. Check for leading stray dot `<p><strong>.</strong></p>`, trailing un-tagged text after final `>`, and outbound direct career URLs.<br/>4. Export audit CSVs and generate drop-in Python cleaning function. |
| **"Check clicks for a specific city/location for [Client]"** | 1. Query `prod_jobiak_ai.job` for jobs with location in that city -> sum clicks across `userAnalytics` (Perspective A: Job Postings).<br/>2. Query `userAnalytics` where `city == target_city` (Perspective B: Job Seekers / Visitors).<br/>3. Identify intersection (Perspective C) and output day-wise breakdown CSV to `antigravity/`. |
"""

# Replace the playbook table rows or append to table
idx_table_end = content.rfind("|")
if idx_table_end != -1:
    content = content[:idx_table_end + 1] + "\n" + playbook_addition.strip() + content[idx_table_end + 1:]

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Updated GEMINI.md successfully. New size: {len(content)} characters.")
