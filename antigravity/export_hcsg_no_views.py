"""
Export HCSG Active Posted Jobs with Zero Views (Pure Human Google Traffic = 0)
==============================================================================
Client: Healthcare Services Group (HCSG)
EmployerId: 6a904f26060e8f0b78b0dc81
Database: prod_jobiak_ai
Collections: job, userAnalytics

Finds all active posted jobs (status == 'posted', isActive == True) that have
received 0 views from organic Google search, along with Googlebot visit counts,
and exports them to a CSV.
"""

import os
import csv
import logging
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("hcsg_zero_views")


def format_date(val):
    if not val:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in .env")

    logger.info("Connecting to MongoDB registry...")
    root_client = MongoClient(mongo_uri)
    creds_col = root_client["mongo_creds"]["creds"]
    cred_doc = creds_col.find_one({"domain": "prod_jobiak_ai"})
    if not cred_doc:
        raise ValueError("prod_jobiak_ai credentials not found")

    prod_client = MongoClient(cred_doc.get("mongo_uri") or cred_doc.get("uri"))
    db = prod_client["prod_jobiak_ai"]

    jobs_col = db["job"]
    analytics_col = db["userAnalytics"]
    emp_id = "6a904f26060e8f0b78b0dc81"

    # 1. Fetch all active posted jobs for HCSG
    logger.info("Fetching active posted jobs for HCSG...")
    query = {
        "employerId": emp_id,
        "status": "posted",
        "isActive": True
    }
    projection = {
        "_id": 0,
        "jobId": 1,
        "clientJobId": 1,
        "title": 1,
        "location": 1,
        "status": 1,
        "isActive": 1,
        "datePosted": 1,
        "validThrough": 1,
        "submittedUrl": 1
    }
    active_jobs = list(jobs_col.find(query, projection))
    logger.info(f"Loaded {len(active_jobs)} active posted jobs.")

    # 2. Aggregate Google organic human views per job
    logger.info("Aggregating Google organic views...")
    p_views = [
        {
            "$match": {
                "employerId": emp_id,
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True
            }
        },
        {"$group": {"_id": "$childJobId", "views": {"$sum": 1}}}
    ]
    views_map = {
        str(r["_id"]): r["views"]
        for r in analytics_col.aggregate(p_views, allowDiskUse=True)
        if r.get("_id")
    }
    logger.info(f"Found {len(views_map)} jobs with at least 1 Google view.")

    # 3. Aggregate Googlebot crawl visits per job
    logger.info("Aggregating Googlebot crawl visits...")
    p_bots = [
        {"$match": {"employerId": emp_id, "isBot": True}},
        {"$group": {"_id": "$childJobId", "bot_visits": {"$sum": 1}}}
    ]
    bot_map = {
        str(r["_id"]): r["bot_visits"]
        for r in analytics_col.aggregate(p_bots, allowDiskUse=True)
        if r.get("_id")
    }
    logger.info(f"Found {len(bot_map)} jobs with at least 1 Googlebot crawl.")

    # 4. Filter jobs with 0 Google views
    zero_views_jobs = []
    for j in active_jobs:
        jid = str(j.get("jobId", "")).strip()
        views = views_map.get(jid, 0)
        if views == 0:
            b_visits = bot_map.get(jid, 0)
            zero_views_jobs.append({
                "jobId": jid,
                "clientJobId": str(j.get("clientJobId", "")).strip(),
                "title": (j.get("title") or "Unknown").strip(),
                "location": (j.get("location") or "Unknown").strip(),
                "status": j.get("status", ""),
                "isActive": str(j.get("isActive")),
                "datePosted": format_date(j.get("datePosted")),
                "validThrough": format_date(j.get("validThrough")),
                "submittedUrl": j.get("submittedUrl", ""),
                "views": 0,
                "bot_visits": b_visits,
                "has_googlebot_visited": "Yes" if b_visits > 0 else "No"
            })

    # Sort: Jobs with NO Googlebot first, then by datePosted
    zero_views_jobs.sort(key=lambda x: (x["bot_visits"], x["datePosted"]), reverse=False)

    logger.info(f"Total HCSG Active Posted Jobs with ZERO views: {len(zero_views_jobs)}")

    # 5. Export to CSV
    output_filename = "HCSG_Active_Jobs_With_Zero_Views.csv"
    output_dirs = [
        r"C:\Users\JOBIAK\Documents\Python",
        r"C:\Users\JOBIAK\Downloads",
        r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
    ]

    fieldnames = [
        "jobId",
        "clientJobId",
        "title",
        "location",
        "status",
        "isActive",
        "datePosted",
        "validThrough",
        "submittedUrl",
        "views",
        "bot_visits",
        "has_googlebot_visited"
    ]

    saved_paths = []
    for d in output_dirs:
        os.makedirs(d, exist_ok=True)
        out_path = os.path.join(d, output_filename)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(zero_views_jobs)
        saved_paths.append(out_path)

    print("\n" + "=" * 65)
    print("HCSG ZERO-VIEWS EXPORT COMPLETED SUCCESSFULLY:")
    print(f"  Total Active Posted Jobs: {len(active_jobs)}")
    print(f"  Jobs with ZERO Google Views: {len(zero_views_jobs)}")
    print(f"    - Of which Googlebot VISITED: {sum(1 for j in zero_views_jobs if j['has_googlebot_visited'] == 'Yes')}")
    print(f"    - Of which Googlebot NEVER VISITED: {sum(1 for j in zero_views_jobs if j['has_googlebot_visited'] == 'No')}")
    print(f"  Output CSV Files: {saved_paths}")
    print("=" * 65)


if __name__ == "__main__":
    main()
