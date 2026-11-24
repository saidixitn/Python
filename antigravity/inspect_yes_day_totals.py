import os
from datetime import datetime
from collections import Counter, defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
rec = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
pj_client = MongoClient(rec["mongo_uri"], serverSelectionTimeoutMS=8000)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

cursor = db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "createdDt": 1, "_id": 0}
).hint("employerId_1")

day_totals = Counter()
job_day_clicks = Counter()
job_lifetime = Counter()

for c in cursor:
    dt = c.get("createdDt")
    jid = c.get("jobId")
    if dt and jid:
        d_str = dt.strftime("%Y-%m-%d")
        day_totals[d_str] += 1
        job_day_clicks[(jid, d_str)] += 1
        job_lifetime[jid] += 1

print("--- TOP 5 DAYS ---")
for d, cnt in day_totals.most_common(5):
    print(f"{d}: {cnt} clicks")

print("\n--- RECENT DAYS ---")
for d in sorted(day_totals.keys())[-5:]:
    print(f"{d}: {day_totals[d]} clicks")
