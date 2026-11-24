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

# Load jobs metadata
all_jobs_cursor = db.job.find(
    {"employerId": emp_id},
    {
        "jobId": 1, "title": 1, "cleansedTitle": 1, "location": 1,
        "locationInfo": 1, "status": 1, "isActive": 1, "datePosted": 1,
        "validThrough": 1, "submittedUrl": 1, "url": 1, "clientJobId": 1, "_id": 0
    }
)

jobs_dict = {}
for j in all_jobs_cursor:
    jid = j.get("jobId")
    if not jid:
        continue
    loc_info = j.get("locationInfo") or {}
    city = loc_info.get("city") or ""
    state = loc_info.get("stageAbbr") or loc_info.get("state") or ""
    if not city and j.get("location"):
        parts = [p.strip() for p in j.get("location", "").split(",")]
        if len(parts) >= 1:
            city = parts[0]
        if len(parts) >= 2:
            state = parts[1]
            
    status_raw = str(j.get("status", "unknown")).strip().lower()
    is_active = bool(j.get("isActive"))
    
    if status_raw == "posted" and is_active:
        status_clean = "Posted"
        active_clean = "Active"
    elif status_raw == "removed" or not is_active:
        status_clean = "Expired"
        active_clean = "Inactive"
    else:
        status_clean = status_raw.capitalize()
        active_clean = "Active" if is_active else "Inactive"
        
    jobs_dict[jid] = {
        "jobId": jid,
        "clientJobId": j.get("clientJobId") or "",
        "title": (j.get("title") or "Unknown Title").strip(),
        "location": (j.get("location") or f"{city}, {state}").strip(),
        "city": city or "Unknown",
        "state": state or "Unknown",
        "status": status_clean,
        "isActive": active_clean,
        "datePosted": j.get("datePosted").strftime("%Y-%m-%d") if j.get("datePosted") else "",
        "validThrough": j.get("validThrough").strftime("%Y-%m-%d") if j.get("validThrough") else "",
        "url": j.get("submittedUrl") or j.get("url") or "",
    }

print(f"Total jobs loaded: {len(jobs_dict)}")

# Load click records from userAnalytics
cursor = db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "createdDt": 1, "_id": 0}
).hint("employerId_1")

clicks_10_19 = Counter()
clicks_10_05 = Counter()
clicks_11_16 = Counter()
clicks_11_17 = Counter()
lifetime_clicks = Counter()

for c in cursor:
    dt = c.get("createdDt")
    jid = c.get("jobId")
    if not dt or not jid:
        continue
    d_str = dt.strftime("%Y-%m-%d")
    lifetime_clicks[jid] += 1
    if d_str == "2026-10-19":
        clicks_10_19[jid] += 1
    elif d_str == "2026-10-05":
        clicks_10_05[jid] += 1
    elif d_str == "2026-11-16":
        clicks_11_16[jid] += 1
    elif d_str == "2026-11-17":
        clicks_11_17[jid] += 1

print(f"Unique jobs clicked on 10-19: {len(clicks_10_19)} (total clicks: {sum(clicks_10_19.values())})")
print(f"Unique jobs clicked on 10-05: {len(clicks_10_05)} (total clicks: {sum(clicks_10_05.values())})")
print(f"Unique jobs clicked on 11-16: {len(clicks_11_16)} (total clicks: {sum(clicks_11_16.values())})")
print(f"Unique jobs clicked on 11-17: {len(clicks_11_17)} (total clicks: {sum(clicks_11_17.values())})")

# Let's see union of jobs clicked on 10-19 OR 11-17 (yesterday)
union_10_19_and_yesterday = set(clicks_10_19.keys()) | set(clicks_11_17.keys())
print(f"Union of jobs clicked on 10-19 OR 11-17: {len(union_10_19_and_yesterday)}")

# Union of all 4 dates
union_all = set(clicks_10_19.keys()) | set(clicks_10_05.keys()) | set(clicks_11_16.keys()) | set(clicks_11_17.keys())
print(f"Union of jobs clicked across all key dates: {len(union_all)}")
