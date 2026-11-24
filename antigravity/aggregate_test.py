import os
from collections import defaultdict, Counter
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
jobs_col = db["job"]
analytics_col = db["userAnalytics"]

print("1. Fetching all jobs for HCSG...")
jobs_cursor = jobs_col.find(
    {"employerId": emp_id},
    {
        "_id": 0, "jobId": 1, "clientJobId": 1, "jobPubJobId": 1,
        "title": 1, "location": 1, "status": 1, "isActive": 1,
        "datePosted": 1, "validThrough": 1, "submittedUrl": 1
    }
)
jobs = list(jobs_cursor)
print(f"Loaded {len(jobs)} jobs.")

jobs_by_id = {}
jobs_by_alias = defaultdict(list)
for j in jobs:
    jid = str(j.get("jobId", "")).strip()
    if jid:
        jobs_by_id[jid] = j
    for alias_field in ("jobId", "clientJobId", "jobPubJobId"):
        val = str(j.get(alias_field, "")).strip()
        if val:
            jobs_by_alias[val].append(j)

print("2. Aggregating analytics counts...")
# A) All non-bot views by childJobId
p_nobot = [
    {"$match": {"employerId": emp_id, "isBot": False}},
    {"$group": {"_id": "$childJobId", "count": {"$sum": 1}}}
]
nobot_counts = {str(r["_id"]): r["count"] for r in analytics_col.aggregate(p_nobot, allowDiskUse=True) if r.get("_id")}

# B) Google non-bot views by childJobId
p_gviews = [
    {
        "$match": {
            "employerId": emp_id,
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True
        }
    },
    {"$group": {"_id": "$childJobId", "count": {"$sum": 1}}}
]
gviews_counts = {str(r["_id"]): r["count"] for r in analytics_col.aggregate(p_gviews, allowDiskUse=True) if r.get("_id")}

# C) Bot visits by childJobId (isBot: True)
p_bot = [
    {"$match": {"employerId": emp_id, "isBot": True}},
    {"$group": {"_id": "$childJobId", "count": {"$sum": 1}}}
]
bot_counts = {str(r["_id"]): r["count"] for r in analytics_col.aggregate(p_bot, allowDiskUse=True) if r.get("_id")}

print(f"Total jobs with nobot views: {len(nobot_counts)}, sum views: {sum(nobot_counts.values())}")
print(f"Total jobs with gviews: {len(gviews_counts)}, sum gviews: {sum(gviews_counts.values())}")
print(f"Total jobs with bot visits: {len(bot_counts)}, sum bot visits: {sum(bot_counts.values())}")

# Check posted jobs bot status
posted_jobs = [j for j in jobs if j.get("status") == "posted" and j.get("isActive") is True]
posted_no_bot = [j for j in posted_jobs if bot_counts.get(str(j.get("jobId", "")), 0) == 0]
print(f"Total posted jobs: {len(posted_jobs)}")
print(f"Posted jobs with NO bot: {len(posted_no_bot)}")
