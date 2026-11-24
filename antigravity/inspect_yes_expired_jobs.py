import os
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from collections import Counter

load_dotenv(r"./.env")
root = MongoClient(os.getenv("MONGO_URI"))
creds = root["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
db = MongoClient(creds["mongo_uri"])["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"
jobs_dict = {j["jobId"]: j for j in db.job.find({"employerId": emp_id})}

clicks = list(db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "childJobId": 1, "createdDt": 1, "_id": 0}
).hint("employerId_1"))

c_1019 = [c for c in clicks if c.get("createdDt") and c["createdDt"].strftime("%Y-%m-%d") == "2026-10-19"]
j_1019 = Counter(c.get("jobId") or c.get("childJobId") for c in c_1019)

print(f"=== 9 EXPIRED JOBS THAT GOT CLICKS ON 10-19 ===")
for jid, cnt in j_1019.items():
    j = jobs_dict.get(jid)
    if j and (j.get("status") != "posted" or not j.get("isActive")):
        print(f"JobID: {jid} | Title: {j.get('title')} | Loc: {j.get('location')} | Clicks 10-19: {cnt} | Status: {j.get('status')} | validThrough: {j.get('validThrough')}")
