#!/usr/bin/env python3
"""
HCSG Job Posting Audit & Feed Classifier Extraction Script
==========================================================
Connects dynamically via MONGO_URI to:
  1. generateXml_prod (emp-gxc-hcsg) - Raw Client XML Feed
  2. jobicarenode_prod (Target_P4_Opt) - Upstream Staging & GEO Expansions
  3. prod_jobiak_ai (job) - Production Google Jobs Indexing Store

Calculates:
  * Total Feed Jobs
  * Total Unique Feed count (Number of unique titles)
  * Total GEO-Expanded Jobs
  * Number of Feed Jobs Posted
  * Number of GEO-Expanded Jobs Posted
  * Number of Feed Jobs Remaining to Be Posted
  * Number of GEO-Expanded Jobs Remaining to Be Posted
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient

# 1. Load Environment & Connect
load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    print("Error: MONGO_URI missing from environment or .env file.")
    sys.exit(1)

root_client = MongoClient(mongo_uri)
creds_col = root_client["mongo_creds"]["creds"]

prod_uri = creds_col.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
jicn_uri = creds_col.find_one({"domain": "jobicarenode_prod"})["mongo_uri"]
gxml_uri = creds_col.find_one({"domain": "generateXml_prod"})["mongo_uri"]

prod_db = MongoClient(prod_uri)["prod_jobiak_ai"]
jicn_db = MongoClient(jicn_uri)["jobicarenode_prod"]
gxml_db = MongoClient(gxml_uri)["generateXml_prod"]

prod_col = prod_db["job"]
jicn_col = jicn_db["Target_P4_Opt"]
gxml_col = gxml_db["emp-gxc-hcsg"]

HCSG_PROD_ID = "6a904f26060e8f0b78b0dc81"
HCSG_JICN_ID = "emp-jicn-hcsg"

print("=" * 75)
print("HEALTHCARE SERVICES GROUP (HCSG) - AUDIT EXTRACTION PIPELINE")
print("=" * 75)

# ---------------------------------------------------------------------------
# STEP 1: Query Raw Client XML Feed (generateXml_prod.emp-gxc-hcsg)
# ---------------------------------------------------------------------------
total_xml_feed_jobs = gxml_col.count_documents({})
raw_xml_titles = gxml_col.distinct("title")
unique_xml_titles = set(t.strip().lower() for t in raw_xml_titles if t)

print(f"\n[1] Client XML Feed (generateXml_prod.emp-gxc-hcsg):")
print(f"    - Total Feed Jobs: {total_xml_feed_jobs:,}")
print(f"    - Unique Feed Count (unique titles): {len(unique_xml_titles)}")

# ---------------------------------------------------------------------------
# STEP 2: Query Upstream Staging / Feeds (jobicarenode_prod.Target_P4_Opt)
# ---------------------------------------------------------------------------
print(f"\n[2] Loading Upstream Jobicare Records (emp-jicn-hcsg)...")
jicn_cursor = jicn_col.find(
    {"employerId": HCSG_JICN_ID},
    {"_id": 0, "uniqueKey": 1, "extraInfo.feedData": 1, "job_status": 1, "gpost": 1, "jobtitle": 1}
)

jicn_map = {}
total_feed_all = 0
active_feed = 0
feed_titles_all = set()
feed_titles_active = set()

total_geo_all = 0
active_geo = 0

for doc in jicn_cursor:
    uk = str(doc.get("uniqueKey", "")).strip()
    status = doc.get("job_status")
    extra_info = doc.get("extraInfo") or {}
    fd = extra_info.get("feedData")
    gpost = doc.get("gpost")
    title = str(doc.get("jobtitle", "")).strip().lower()

    is_feed = (fd == 1 or fd == "1")
    is_geo = (fd == 0 or fd == "0")

    if is_feed:
        total_feed_all += 1
        if title:
            feed_titles_all.add(title)
        if status != 3:
            active_feed += 1
            if title:
                feed_titles_active.add(title)
    elif is_geo:
        total_geo_all += 1
        if status != 3:
            active_geo += 1

    if uk:
        jicn_map[uk] = {
            "feedData": fd,
            "is_feed": is_feed,
            "is_geo": is_geo,
            "job_status": status,
            "gpost": gpost,
            "title": title
        }

print(f"    - Total Jobicare Docs Loaded: {len(jicn_map):,}")
print(f"    - Active Feed Jobs (job_status != 3): {active_feed:,} (Unique titles: {len(feed_titles_active)})")
print(f"    - All-Time Feed Jobs: {total_feed_all:,} (Unique titles: {len(feed_titles_all)})")
print(f"    - Active GEO-Expanded Jobs (job_status != 3): {active_geo:,}")
print(f"    - All-Time GEO-Expanded Jobs: {total_geo_all:,}")

# ---------------------------------------------------------------------------
# STEP 3: Match Production Posted Jobs (prod_jobiak_ai.job)
# ---------------------------------------------------------------------------
print(f"\n[3] Matching Against Production Posted Jobs (employerId: {HCSG_PROD_ID})...")

# Currently Live Active Posted Jobs
prod_active_jobs = list(prod_col.find(
    {"employerId": HCSG_PROD_ID, "status": "posted", "isActive": True},
    {"_id": 0, "clientJobId": 1, "title": 1}
))

active_posted_keys = set()
posted_active_feed = 0
posted_active_geo = 0
posted_active_unmatched = 0

for j in prod_active_jobs:
    cjid = str(j.get("clientJobId", "")).strip()
    active_posted_keys.add(cjid)
    info = jicn_map.get(cjid)
    if info:
        if info["is_feed"]:
            posted_active_feed += 1
        elif info["is_geo"]:
            posted_active_geo += 1
        else:
            posted_active_unmatched += 1
    else:
        posted_active_unmatched += 1

# All-Time Production Jobs (including removed / historical)
prod_all_jobs = list(prod_col.find(
    {"employerId": HCSG_PROD_ID},
    {"_id": 0, "clientJobId": 1}
))
all_prod_keys = set(str(j.get("clientJobId", "")).strip() for j in prod_all_jobs if j.get("clientJobId"))

all_posted_feed = 0
all_posted_geo = 0
for cjid in all_prod_keys:
    info = jicn_map.get(cjid)
    if info:
        if info["is_feed"]:
            all_posted_feed += 1
        elif info["is_geo"]:
            all_posted_geo += 1

print(f"    - Currently Active Posted Jobs in Prod: {len(prod_active_jobs):,}")
print(f"      * Feed Jobs Posted (Active): {posted_active_feed:,}")
print(f"      * GEO-Expanded Jobs Posted (Active): {posted_active_geo:,}")
print(f"      * Unmatched: {posted_active_unmatched}")
print(f"    - All-Time Production Jobs: {len(all_prod_keys):,}")
print(f"      * Feed Jobs Posted (All-Time): {all_posted_feed:,}")
print(f"      * GEO-Expanded Jobs Posted (All-Time): {all_posted_geo:,}")

# ---------------------------------------------------------------------------
# STEP 4: Calculate Remaining Jobs to Post (Eligible Queue)
# ---------------------------------------------------------------------------
# feed.py logic: job_status != 3, gpost in [1, 3], uniqueKey not in production
remaining_feed_pipeline = 0
remaining_geo_pipeline = 0

# Alternative: excluding only currently live active jobs
remaining_feed_vs_active = 0
remaining_geo_vs_active = 0

remaining_feed_titles = set()

for uk, info in jicn_map.items():
    if info["job_status"] != 3 and info["gpost"] in [1, 3]:
        # Exclude all production jobs (feed.py standard)
        if uk not in all_prod_keys:
            if info["is_feed"]:
                remaining_feed_pipeline += 1
                if info["title"]:
                    remaining_feed_titles.add(info["title"])
            elif info["is_geo"]:
                remaining_geo_pipeline += 1

        # Exclude only currently live active jobs
        if uk not in active_posted_keys:
            if info["is_feed"]:
                remaining_feed_vs_active += 1
            elif info["is_geo"]:
                remaining_geo_vs_active += 1

# ---------------------------------------------------------------------------
# STEP 5: Final Results Display
# ---------------------------------------------------------------------------
print("\n" + "=" * 75)
print("FINAL AUDIT RESULTS FOR HCSG")
print("=" * 75)
print(f"* Total Feed Jobs:                              {total_xml_feed_jobs:,} (Client XML) / {active_feed:,} (Active Jobicare)")
print(f"* Total Unique Feed count (No. unique titles): {len(unique_xml_titles)} (Client XML) / {len(feed_titles_active)} (Active Jobicare)")
print(f"* Total GEO-Expanded Jobs:                     {active_geo:,} (Active) / {total_geo_all:,} (All-Time)")
print(f"* Number of Feed Jobs Posted:                   {posted_active_feed:,} (Currently Live) / {all_posted_feed:,} (All-Time)")
print(f"* Number of GEO-Expanded Jobs Posted:           {posted_active_geo:,} (Currently Live) / {all_posted_geo:,} (All-Time)")
print(f"* Number of Feed Jobs Remaining to Be Posted:   {remaining_feed_pipeline:,} (vs All Prod) / {remaining_feed_vs_active:,} (vs Active)")
print(f"* Number of GEO-Expanded Jobs Remaining:        {remaining_geo_pipeline:,} (vs All Prod) / {remaining_geo_vs_active:,} (vs Active)")
print(f"  -> Distinct titles ready to post in feed:     {len(remaining_feed_titles)}")
print("=" * 75)
