import os
from collections import defaultdict, Counter
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(r"./.env")
root = MongoClient(os.getenv("MONGO_URI"))
creds = root["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
db = MongoClient(creds["mongo_uri"])["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

# Load jobs
jobs_dict = {}
for j in db.job.find({"employerId": emp_id}):
    jobs_dict[j["jobId"]] = j

print(f"Loaded {len(jobs_dict)} jobs.")

# Fetch all clicks
clicks = list(db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "childJobId": 1, "createdDt": 1, "ipAddress": 1, "deviceType": 1, "_id": 0}
).hint("employerId_1"))

print(f"Total Google clicks: {len(clicks)}")

# Breakdown by title on 10-19 vs 11-16
title_clicks_1019 = Counter()
title_clicks_1116 = Counter()
title_clicks_total = Counter()

loc_clicks_1019 = Counter()
loc_clicks_1116 = Counter()
loc_clicks_total = Counter()

combo_clicks_1019 = Counter()
combo_clicks_1116 = Counter()
combo_clicks_total = Counter()

for c in clicks:
    jid = c.get("jobId") or c.get("childJobId")
    j = jobs_dict.get(jid)
    title = (j.get("title") or "Unknown Title").strip() if j else "Unknown / Deleted"
    loc = (j.get("location") or "Unknown Location").strip() if j else "Unknown Location"
    dt = c.get("createdDt")
    d_str = dt.strftime("%Y-%m-%d") if dt else "Unknown"

    title_clicks_total[title] += 1
    loc_clicks_total[loc] += 1
    combo_clicks_total[(title, loc)] += 1

    if d_str == "2026-10-19":
        title_clicks_1019[title] += 1
        loc_clicks_1019[loc] += 1
        combo_clicks_1019[(title, loc)] += 1
    elif d_str == "2026-11-16":
        title_clicks_1116[title] += 1
        loc_clicks_1116[loc] += 1
        combo_clicks_1116[(title, loc)] += 1

print("\n=== TOP TITLES ON 10-19 vs 11-16 ===")
for title in sorted(set(list(title_clicks_1019.keys()) + list(title_clicks_1116.keys())), key=lambda t: title_clicks_1019[t], reverse=True):
    c1 = title_clicks_1019[title]
    c2 = title_clicks_1116[title]
    tot = title_clicks_total[title]
    print(f"Title: {title[:40]:<40} | 10-19: {c1:2d} | 11-16: {c2:2d} | Diff: {c2-c1:+3d} | Total: {tot:3d}")

print("\n=== TOP LOCATIONS ON 10-19 vs 11-16 ===")
for loc in sorted(set(list(loc_clicks_1019.keys()) + list(loc_clicks_1116.keys())), key=lambda l: loc_clicks_1019[l], reverse=True)[:10]:
    c1 = loc_clicks_1019[loc]
    c2 = loc_clicks_1116[loc]
    tot = loc_clicks_total[loc]
    print(f"Location: {loc[:35]:<35} | 10-19: {c1:2d} | 11-16: {c2:2d} | Diff: {c2-c1:+3d} | Total: {tot:3d}")
