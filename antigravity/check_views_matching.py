import sys, os
sys.stdout.reconfigure(line_buffering=True)
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
root = MongoClient(mongo_uri)
cred = root["mongo_creds"]["creds"].find_one({"domain": "directclients_prod"})
dc_client = MongoClient(cred["mongo_uri"])
dc_db = dc_client["directclients_prod"]

jobs_col = dc_db["Target_P4_Opt"]
analytics_col = dc_db["userAnalytics"]
emp_id = "emp-jbk-lettuce"

print("Fetching jobs...")
jobs = list(jobs_col.find({"employerId": emp_id}, {"_id": 1, "jobPubJobId": 1, "jobtitle": 1, "location": 1}))
print(f"Loaded {len(jobs)} jobs.")

print("Aggregating Google views...")
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
    {"$group": {"_id": "$jobPubJobId", "views": {"$sum": 1}}}
]
views = list(analytics_col.aggregate(p_views, allowDiskUse=True))
print(f"Distinct jobs with Google views: {len(views)}, Total views: {sum(v['views'] for v in views)}")

print("Aggregating Bot visits...")
p_bot = [
    {"$match": {"employerId": emp_id, "isBot": True}},
    {"$group": {"_id": "$jobPubJobId", "visits": {"$sum": 1}}}
]
bots = list(analytics_col.aggregate(p_bot, allowDiskUse=True))
print(f"Distinct jobs with Bot visits: {len(bots)}, Total bot visits: {sum(b['visits'] for b in bots)}")
