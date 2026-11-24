import os
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import Counter

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds_col = primary_client["mongo_creds"]["creds"]

prod_uri = creds_col.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
jicn_uri = creds_col.find_one({"domain": "jobicarenode_prod"})["mongo_uri"]

prod_db = MongoClient(prod_uri)["prod_jobiak_ai"]
jicn_db = MongoClient(jicn_uri)["jobicarenode_prod"]

qrm_prod_id = "6a7b516d060e8f0b78b0dc5a"
qrm_jicn_id = "emp-jicn-qrm"

# 1. Fetch all Jobicare docs for QRM
print("Fetching QRM jobs from Jobicare...")
jicn_cursor = jicn_db["Target_P4_Opt"].find(
    {"employerId": qrm_jicn_id},
    {"_id": 0, "uniqueKey": 1, "extraInfo.feedData": 1, "job_status": 1, "gpost": 1}
)

jicn_jobs = list(jicn_cursor)
print(f"Total Jobicare QRM docs loaded: {len(jicn_jobs)}")

total_feed_all = 0
total_expanded_all = 0
active_feed = 0
active_expanded = 0

jicn_map = {}
for doc in jicn_jobs:
    uk = str(doc.get("uniqueKey", "")).strip()
    status = doc.get("job_status")
    extra_info = doc.get("extraInfo") or {}
    fd = extra_info.get("feedData")
    
    # 1 = feed, 0 = expanded
    is_feed = (fd == 1 or fd == "1")
    is_expanded = (fd == 0 or fd == "0")
    
    if is_feed:
        total_feed_all += 1
        if status != 3:
            active_feed += 1
    elif is_expanded:
        total_expanded_all += 1
        if status != 3:
            active_expanded += 1

    if uk:
        jicn_map[uk] = {
            "is_feed": is_feed,
            "is_expanded": is_expanded,
            "job_status": status,
            "gpost": doc.get("gpost")
        }

# 2. Fetch all Production posted jobs for QRM
print("Fetching QRM jobs from Production...")
prod_jobs = list(prod_db["job"].find(
    {"employerId": qrm_prod_id, "status": "posted", "isActive": True},
    {"_id": 0, "clientJobId": 1, "jobId": 1}
))
print(f"Total Production Active Posted jobs loaded: {len(prod_jobs)}")

posted_feed = 0
posted_expanded = 0
posted_unmatched = 0

for j in prod_jobs:
    cjid = str(j.get("clientJobId", "")).strip()
    if cjid in jicn_map:
        info = jicn_map[cjid]
        if info["is_feed"]:
            posted_feed += 1
        elif info["is_expanded"]:
            posted_expanded += 1
    else:
        posted_unmatched += 1

print("\n" + "="*50)
print("FINAL RESULTS FOR QRM:")
print(f"Total Feed Jobs in Jobicare (all): {total_feed_all}")
print(f"Active Feed Jobs in Jobicare (job_status != 3): {active_feed}")
print(f"Total Expanded Jobs in Jobicare (all): {total_expanded_all}")
print(f"Active Expanded Jobs in Jobicare (job_status != 3): {active_expanded}")
print(f"Total Production Active Posted Jobs: {len(prod_jobs)}")
print(f"  -> No. of Feed Jobs Posted: {posted_feed}")
print(f"  -> No. of Expanded Jobs Posted: {posted_expanded}")
if posted_unmatched > 0:
    print(f"  -> Unmatched in Jobicare: {posted_unmatched}")
print("="*50)
