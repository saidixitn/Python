import os
from collections import Counter, defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
rec = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
pj_client = MongoClient(rec["mongo_uri"], serverSelectionTimeoutMS=8000)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

print("Step 1: Finding Indianapolis jobs in YES Communities...")
# Check jobs with Indianapolis in location
job_cursor = db.job.find(
    {"employerId": emp_id},
    {
        "jobId": 1, "title": 1, "location": 1, "locationInfo": 1,
        "status": 1, "isActive": 1, "datePosted": 1, "validThrough": 1
    }
)

indy_jobs = {}
all_jobs = {}
for j in job_cursor:
    jid = j.get("jobId")
    if not jid:
        continue
    all_jobs[jid] = j
    loc = j.get("location", "")
    loc_info = j.get("locationInfo") or {}
    city = loc_info.get("city") or ""
    
    is_indy = False
    if "indianapolis" in loc.lower():
        is_indy = True
    elif "indianapolis" in city.lower():
        is_indy = True
        
    if is_indy:
        indy_jobs[jid] = j

print(f"Total YES Communities jobs: {len(all_jobs)}")
print(f"Total Indianapolis jobs found: {len(indy_jobs)}")
for jid, j in list(indy_jobs.items())[:5]:
    print(f"  {jid} | {j.get('title')} | {j.get('location')} | status: {j.get('status')} | active: {j.get('isActive')}")

print("\nStep 2: Fetching userAnalytics Google clicks...")
analytics_cursor = db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {
        "jobId": 1, "createdDt": 1, "city": 1, "region": 1, "country": 1,
        "ipAddress": 1, "deviceType": 1, "_id": 0
    }
).hint("employerId_1")

clicks = list(analytics_cursor)
print(f"Total Google clicks for YES Communities: {len(clicks)}")

# Perspective A: Clicks on Indianapolis Jobs
indy_job_day_clicks = Counter()
indy_job_clicks_by_job = Counter()

# Perspective B: Clicks from Indianapolis Visitors
indy_visitor_day_clicks = Counter()
indy_visitor_jobs_clicked = Counter()

# Perspective C: Both (Indianapolis Job AND Indianapolis Visitor)
both_day_clicks = Counter()

for c in clicks:
    jid = c.get("jobId")
    dt = c.get("createdDt")
    if not dt:
        continue
    d_str = dt.strftime("%Y-%m-%d")
    
    # Check if job is in Indianapolis
    if jid in indy_jobs:
        indy_job_day_clicks[d_str] += 1
        indy_job_clicks_by_job[jid] += 1
        
    # Check if visitor is in Indianapolis
    v_city = (c.get("city") or "").strip().lower()
    v_region = (c.get("region") or "").strip().lower()
    if v_city == "indianapolis":
        indy_visitor_day_clicks[d_str] += 1
        if jid:
            indy_visitor_jobs_clicked[jid] += 1
            
    if jid in indy_jobs and v_city == "indianapolis":
        both_day_clicks[d_str] += 1

print("\n--- RESULTS: PERSPECTIVE A (Clicks on Indianapolis Job Postings) ---")
print(f"Total clicks on Indianapolis jobs: {sum(indy_job_day_clicks.values())}")
print(f"Unique Indianapolis jobs clicked: {len(indy_job_clicks_by_job)}")
for d in sorted(indy_job_day_clicks.keys()):
    print(f"  {d}: {indy_job_day_clicks[d]} clicks")

print("\n--- RESULTS: PERSPECTIVE B (Clicks from Visitors in Indianapolis) ---")
print(f"Total clicks from Indianapolis visitors: {sum(indy_visitor_day_clicks.values())}")
for d in sorted(indy_visitor_day_clicks.keys()):
    print(f"  {d}: {indy_visitor_day_clicks[d]} clicks")

print("\n--- RESULTS: PERSPECTIVE C (Both Indianapolis Job AND Visitor) ---")
print(f"Total clicks where both job and visitor are in Indianapolis: {sum(both_day_clicks.values())}")
for d in sorted(both_day_clicks.keys()):
    print(f"  {d}: {both_day_clicks[d]} clicks")
