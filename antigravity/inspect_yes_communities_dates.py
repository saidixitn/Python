import os
from datetime import datetime, timezone
from collections import Counter
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(r"./.env")
root = MongoClient(os.getenv("MONGO_URI"))
creds = root["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
db = MongoClient(creds["mongo_uri"])["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

# Check daily clicks for YES Communities
pipeline = [
    {
        "$match": {
            "employerId": emp_id,
            "isFromGoogle": True,
            "isBot": False
        }
    },
    {
        "$group": {
            "_id": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$createdDt"
                }
            },
            "clicks": {"$sum": 1}
        }
    },
    {"$sort": {"_id": -1}}
]

daily_clicks = list(db.userAnalytics.aggregate(pipeline, allowDiskUse=True))
print("=== Top 10 Recent Dates with Clicks ===")
for d in daily_clicks[:15]:
    print(f"Date: {d['_id']} -> Clicks: {d['clicks']}")

print("\n=== Top 5 Max Click Dates ===")
sorted_by_clicks = sorted(daily_clicks, key=lambda x: x["clicks"], reverse=True)
for d in sorted_by_clicks[:5]:
    print(f"Date: {d['_id']} -> Clicks: {d['clicks']}")

# Check 10-19 specifically
c_1019 = [d for d in daily_clicks if "10-19" in str(d["_id"])]
print(f"\n10-19 Clicks: {c_1019}")

# Check total jobs and status
jobs_count = db.job.count_documents({"employerId": emp_id})
posted_count = db.job.count_documents({"employerId": emp_id, "status": "posted", "isActive": True})
removed_count = db.job.count_documents({"employerId": emp_id, "status": "removed"})
inactive_count = db.job.count_documents({"employerId": emp_id, "isActive": False})
print(f"\nJobs Summary: Total={jobs_count}, Active Posted={posted_count}, Removed={removed_count}, Inactive={inactive_count}")
