import os
from collections import Counter, defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
rec = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
pj_client = MongoClient(rec["mongo_uri"], serverSelectionTimeoutMS=8000)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

# Load Indianapolis jobs
job_cursor = db.job.find(
    {"employerId": emp_id, "location": {"$regex": "Indianapolis", "$options": "i"}},
    {
        "jobId": 1, "title": 1, "location": 1, "status": 1, "isActive": 1,
        "datePosted": 1, "validThrough": 1, "submittedUrl": 1, "url": 1
    }
)
indy_jobs = {j["jobId"]: j for j in job_cursor}

analytics_cursor = db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "createdDt": 1, "city": 1, "region": 1, "deviceType": 1, "ipAddress": 1, "_id": 0}
).hint("employerId_1")

clicks = list(analytics_cursor)

# Job breakdown for Indianapolis jobs
job_day_clicks = defaultdict(Counter)
job_total_clicks = Counter()
job_visitor_cities = defaultdict(Counter)

for c in clicks:
    jid = c.get("jobId")
    dt = c.get("createdDt")
    if not dt or jid not in indy_jobs:
        continue
    d_str = dt.strftime("%Y-%m-%d")
    job_day_clicks[jid][d_str] += 1
    job_total_clicks[jid] += 1
    v_city = c.get("city") or "Unknown"
    job_visitor_cities[jid][v_city] += 1

print("--- INDIANAPOLIS JOBS PERFORMANCE ---")
for jid, j in indy_jobs.items():
    tot = job_total_clicks[jid]
    print(f"\nJob ID: {jid}")
    print(f"Title: {j.get('title')}")
    print(f"Status: {j.get('status')} | Active: {j.get('isActive')}")
    print(f"Date Posted: {j.get('datePosted')} | Valid Through: {j.get('validThrough')}")
    print(f"Total Clicks: {tot}")
    if tot > 0:
        print("  Day-wise clicks:")
        for d in sorted(job_day_clicks[jid].keys()):
            print(f"    {d}: {job_day_clicks[jid][d]} click(s)")
        print(f"  Visitor cities: {dict(job_visitor_cities[jid])}")
