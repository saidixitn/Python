import os
from datetime import datetime
from collections import defaultdict, Counter
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(r"./.env")
root = MongoClient(os.getenv("MONGO_URI"))
creds = root["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
db = MongoClient(creds["mongo_uri"])["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

# Load jobs
jobs = {j["jobId"]: j for j in db.job.find({"employerId": emp_id})}

# Fetch all Google clicks for YES Communities using employerId_1 index
all_clicks = list(db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "childJobId": 1, "createdDt": 1, "ipAddress": 1, "city": 1, "region": 1, "country": 1, "_id": 0}
).hint("employerId_1"))

print(f"Total Google clicks fetched: {len(all_clicks)}")

c_1019 = []
c_1116 = []

for c in all_clicks:
    dt = c.get("createdDt")
    if dt:
        d_str = dt.strftime("%Y-%m-%d")
        if d_str == "2026-10-19":
            c_1019.append(c)
        elif d_str == "2026-11-16":
            c_1116.append(c)

print(f"10-19 clicks: {len(c_1019)}")
print(f"11-16 clicks: {len(c_1116)}")

j_1019 = Counter(c.get("jobId") or c.get("childJobId") for c in c_1019)
j_1116 = Counter(c.get("jobId") or c.get("childJobId") for c in c_1116)

print(f"Unique jobs clicked on 10-19: {len(j_1019)}")
print(f"Unique jobs clicked on 11-16: {len(j_1116)}")

status_1019 = Counter()
for jid, count in j_1019.items():
    job = jobs.get(jid)
    if job:
        st = "Active (Posted)" if job.get("status") == "posted" and job.get("isActive") else f"Expired ({job.get('status')})"
    else:
        st = "Deleted / Not Found"
    status_1019[st] += count

print("\nClicks on 10-19 by current job status:")
for st, cnt in status_1019.items():
    print(f"  {st}: {cnt} clicks")

status_1116 = Counter()
for jid, count in j_1116.items():
    job = jobs.get(jid)
    if job:
        st = "Active (Posted)" if job.get("status") == "posted" and job.get("isActive") else f"Expired ({job.get('status')})"
    else:
        st = "Deleted / Not Found"
    status_1116[st] += count

print("\nClicks on 11-16 by current job status:")
for st, cnt in status_1116.items():
    print(f"  {st}: {cnt} clicks")

common_jobs = set(j_1019.keys()) & set(j_1116.keys())
print(f"\nJobs clicked on BOTH days: {len(common_jobs)}")
