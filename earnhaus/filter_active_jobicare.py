import os
import re
import csv
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# Connect to prod_jobiak_ai
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

# Connect to jobicarenode_prod
jicn_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(jicn_creds["mongo_uri"])
db_jicn = jicn_client["jobicarenode_prod"]

print("1. Loading Jobicare status mapping for emp-jicn-qrm...")
# We check Target_P4_Opt and emp-qrm
status_map = {}

# From Target_P4_Opt
for doc in db_jicn["Target_P4_Opt"].find({"employerId": "emp-jicn-qrm"}, {"uniqueKey": 1, "clientJobId": 1, "job_status": 1}):
    st = doc.get("job_status")
    uk = doc.get("uniqueKey")
    cjid = doc.get("clientJobId")
    if uk:
        status_map[uk] = st
    if cjid:
        status_map[cjid] = st

print(f"Loaded {len(status_map)} keys from Target_P4_Opt.")

# Also augment with emp-qrm if not present
for doc in db_jicn["emp-qrm"].find({"employerId": "emp-jicn-qrm"}, {"uniqueKey": 1, "clientJobId": 1, "job_status": 1}):
    st = doc.get("job_status")
    uk = doc.get("uniqueKey")
    cjid = doc.get("clientJobId")
    if uk and uk not in status_map:
        status_map[uk] = st
    if cjid and cjid not in status_map:
        status_map[cjid] = st

print(f"Total keys in status_map after emp-qrm: {len(status_map)}")

# 2. Read our 2,316 posted jobs with NO location in description
df_no_loc = pd.read_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_no_location_dateposted.csv")
print(f"Total posted jobs with NO location: {len(df_no_loc)}")

# We also need clientJobId for each jobId from prod_jobiak_ai.job
job_ids = df_no_loc["jobId"].tolist()
print("Fetching clientJobIds for these 2,316 jobs...")
job_docs = list(job_col.find({"jobId": {"$in": job_ids}}, {"jobId": 1, "clientJobId": 1, "datePosted": 1, "title": 1, "location": 1, "submittedUrl": 1}))
job_doc_map = {d["jobId"]: d for d in job_docs}

active_jobs = []
expired_jobs = []
not_found_jobs = []

for row in df_no_loc.to_dict("records"):
    jid = row["jobId"]
    doc = job_doc_map.get(jid, {})
    cjid = doc.get("clientJobId", "")
    date_posted = row.get("datePosted", "")
    title = row.get("title", "")
    loc = row.get("location", "")
    url = row.get("submittedUrl", "")
    
    # lookup status in jobicare
    jicn_status = status_map.get(cjid)
    
    if jicn_status is None:
        not_found_jobs.append((jid, cjid))
    elif jicn_status == 3:
        expired_jobs.append({
            "jobId": jid,
            "clientJobId": cjid,
            "datePosted": date_posted,
            "job_status": jicn_status
        })
    elif jicn_status in [1, 2]:
        active_jobs.append({
            "jobId": jid,
            "datePosted": date_posted,
            "clientJobId": cjid,
            "job_status": jicn_status,
            "title": title,
            "location": loc,
            "submittedUrl": url
        })
    else:
        # any other status
        print(f"Other status for {jid}: {jicn_status}")

print(f"\n--- FILTER RESULTS ---")
print(f"Active Jobs (job_status in [1, 2]): {len(active_jobs)}")
print(f"Expired Jobs (job_status == 3): {len(expired_jobs)}")
print(f"Not found in Jobicare: {len(not_found_jobs)}")

# Sort active jobs by datePosted descending
active_jobs.sort(key=lambda x: str(x.get("datePosted", "")), reverse=True)

# Save the filtered results
out_2col = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_active_jobids_dateposted.csv"
artifact_2col = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_active_jobids_dateposted.csv"

for p in [out_2col, artifact_2col]:
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jobId", "datePosted"])
        writer.writeheader()
        for aj in active_jobs:
            writer.writerow({"jobId": aj["jobId"], "datePosted": aj["datePosted"]})

out_full = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_active_jobs_no_location_dateposted.csv"
artifact_full = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_active_jobs_no_location_dateposted.csv"

for p in [out_full, artifact_full]:
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jobId", "datePosted", "clientJobId", "job_status", "title", "location", "submittedUrl"])
        writer.writeheader()
        writer.writerows(active_jobs)

print("Saved active filtered CSVs successfully!")
