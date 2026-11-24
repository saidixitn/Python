import os
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import Counter

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
col = db["userAnalytics"]

# Aggregating no-bot views by childJobId
pipeline_all = [
    {"$match": {"employerId": emp_id, "isBot": False}},
    {"$group": {"_id": "$childJobId", "views": {"$sum": 1}}}
]
res_all = list(col.aggregate(pipeline_all))
print(f"Distinct childJobIds with isBot: False views: {len(res_all)}")
total_no_bot_views = sum(r['views'] for r in res_all)
print(f"Total isBot: False views: {total_no_bot_views}")

# Aggregating google views
pipeline_google = [
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
res_google = list(col.aggregate(pipeline_google))
print(f"Distinct childJobIds with Google views: {len(res_google)}")
total_google_views = sum(r['views'] for r in res_google)
print(f"Total Google views: {total_google_views}")
