import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds_col = primary_client["mongo_creds"]["creds"]

prod_uri = creds_col.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
jicn_uri = creds_col.find_one({"domain": "jobicarenode_prod"})["mongo_uri"]

prod_db = MongoClient(prod_uri)["prod_jobiak_ai"]
jicn_db = MongoClient(jicn_uri)["jobicarenode_prod"]

qrm_prod_id = "6a7b516d060e8f0b78b0dc81" # wait, earlier we found qrm_prod_id = "6a7b516d060e8f0b78b0dc5a"
qrm_prod_id = "6a7b516d060e8f0b78b0dc5a"
qrm_jicn_id = "emp-jicn-qrm"

# Fetch all production posted jobs
prod_jobs = list(prod_db["job"].find(
    {"employerId": qrm_prod_id, "status": "posted", "isActive": True},
    {"_id": 0, "clientJobId": 1, "jobId": 1}
))
print(f"Total production active posted jobs: {len(prod_jobs)}")

# Get all unique clientJobIds from posted jobs
posted_client_job_ids = [j.get("clientJobId") for j in prod_jobs if j.get("clientJobId")]
print(f"Unique clientJobIds in posted jobs: {len(set(posted_client_job_ids))}")

# Check matching in Jobicare Target_P4_Opt
jicn_col = jicn_db["Target_P4_Opt"]

# Query in batches
feed_posted = 0
expanded_posted = 0
unmatched_posted = 0
other_posted = 0

batch_size = 1000
for i in range(0, len(posted_client_job_ids), batch_size):
    batch = posted_client_job_ids[i:i+batch_size]
    cursor = jicn_col.find(
        {"employerId": qrm_jicn_id, "uniqueKey": {"$in": batch}},
        {"_id": 0, "uniqueKey": 1, "extraInfo.feedData": 1}
    )
    batch_map = {}
    for doc in cursor:
        uk = doc.get("uniqueKey")
        fd = (doc.get("extraInfo") or {}).get("feedData")
        batch_map[uk] = fd
    
    for cjid in batch:
        if cjid not in batch_map:
            unmatched_posted += 1
        elif batch_map[cjid] == 1 or batch_map[cjid] == "1":
            feed_posted += 1
        elif batch_map[cjid] == 0 or batch_map[cjid] == "0":
            expanded_posted += 1
        else:
            other_posted += 1

print(f"Posted Feed Jobs (feedData: 1): {feed_posted}")
print(f"Posted Expanded Jobs (feedData: 0): {expanded_posted}")
print(f"Posted Unmatched in Jobicare: {unmatched_posted}")
print(f"Posted Other/Unknown: {other_posted}")
