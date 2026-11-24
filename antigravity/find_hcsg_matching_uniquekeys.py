import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))

# 1. Connect to jobicarenode_prod
rec_jicn = client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(rec_jicn["mongo_uri"], serverSelectionTimeoutMS=8000)
db_jicn = jicn_client["jobicarenode_prod"]

# 2. Connect to prod_jobiak_ai
rec_pj = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
pj_client = MongoClient(rec_pj["mongo_uri"], serverSelectionTimeoutMS=8000)
db_pj = pj_client["prod_jobiak_ai"]

print("Fetching jobs from jobicarenode_prod.Target_P4_Opt...")
query_jicn = {
    "employerId": "emp-jicn-hcsg",
    "job_status": {"$ne": 3},
    "gpost": {"$in": [1, 3, 1.0, 3.0]},
    "jobtitle": {
        "$in": [
            "Dietary Aide",
            "Registered Dietitian",
            "Laundry Worker",
            "Cook",
            "Housekeeper"
        ]
    }
}

cursor_jicn = db_jicn.Target_P4_Opt.find(
    query_jicn,
    {"uniqueKey": 1, "jobtitle": 1, "uncleanedLocation": 1, "gpost": 1, "job_status": 1, "_id": 0}
)
jicn_jobs = list(cursor_jicn)
print(f"Total jobs from jobicarenode_prod: {len(jicn_jobs)}")

jicn_map = {}
for j in jicn_jobs:
    uk = j.get("uniqueKey")
    if uk:
        jicn_map[uk] = j

print(f"Total uniqueKeys from jobicarenode: {len(jicn_map)}")

# Fetch all HCSG jobs in prod_jobiak_ai
hcsg_emp_id = "6a904f26060e8f0b78b0dc81"
print("Fetching all HCSG jobs from prod_jobiak_ai.job...")
cursor_pj = db_pj.job.find(
    {"employerId": hcsg_emp_id},
    {
        "jobId": 1, "clientJobId": 1, "uniqueKey": 1, "title": 1,
        "status": 1, "isActive": 1, "location": 1, "datePosted": 1,
        "validThrough": 1, "url": 1, "submittedUrl": 1, "_id": 0
    }
)
pj_jobs = list(cursor_pj)
print(f"Total HCSG jobs in prod_jobiak_ai: {len(pj_jobs)}")

# Index prod_jobiak_ai jobs by clientJobId and uniqueKey
pj_by_uniquekey = {}
for j in pj_jobs:
    cjid = j.get("clientJobId")
    uk = j.get("uniqueKey")
    if cjid:
        pj_by_uniquekey[cjid] = j
    if uk:
        pj_by_uniquekey[uk] = j

print(f"Indexed {len(pj_by_uniquekey)} uniqueKeys / clientJobIds in prod_jobiak_ai.")

# Find intersection: which uniqueKeys from jobicare are present in prod_jobiak_ai
matched_keys = []
for uk, jicn_job in jicn_map.items():
    if uk in pj_by_uniquekey:
        pj_job = pj_by_uniquekey[uk]
        matched_keys.append({
            "uniqueKey": uk,
            "Job Title (jobicare)": jicn_job.get("jobtitle"),
            "Location (jobicare)": jicn_job.get("uncleanedLocation"),
            "gpost (jobicare)": jicn_job.get("gpost"),
            "job_status (jobicare)": jicn_job.get("job_status"),
            "Job ID (prod_jobiak_ai)": pj_job.get("jobId"),
            "Title (prod_jobiak_ai)": pj_job.get("title"),
            "Status (prod_jobiak_ai)": pj_job.get("status"),
            "isActive (prod_jobiak_ai)": pj_job.get("isActive"),
            "Location (prod_jobiak_ai)": pj_job.get("location"),
            "Date Posted": str(pj_job.get("datePosted")),
            "Valid Through": str(pj_job.get("validThrough")),
            "Submitted URL": pj_job.get("submittedUrl") or pj_job.get("url") or ""
        })

print(f"\n==========================================")
print(f"MATCHED UNIQUEKEYS FOUND: {len(matched_keys)} / {len(jicn_map)}")
print(f"==========================================")

df_matched = pd.DataFrame(matched_keys)
if not df_matched.empty:
    print("\nBreakdown by prod_jobiak_ai status:")
    print(df_matched["Status (prod_jobiak_ai)"].value_counts())
    print("\nBreakdown by prod_jobiak_ai isActive:")
    print(df_matched["isActive (prod_jobiak_ai)"].value_counts())
    print("\nBreakdown by Job Title:")
    print(df_matched["Job Title (jobicare)"].value_counts())

    out_csv = r"c:\Users\JOBIAK\Documents\Python\antigravity\HCSG_Jobicare_vs_ProdJobiak_Duplicate_UniqueKeys.csv"
    artifact_csv = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6\HCSG_Jobicare_vs_ProdJobiak_Duplicate_UniqueKeys.csv"
    df_matched.to_csv(out_csv, index=False)
    df_matched.to_csv(artifact_csv, index=False)
    print(f"Saved CSV to {out_csv} and artifact dir.")

    # Also save simple list of uniqueKeys
    out_txt = r"c:\Users\JOBIAK\Documents\Python\antigravity\HCSG_Present_UniqueKeys_List.txt"
    artifact_txt = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6\HCSG_Present_UniqueKeys_List.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        for m in matched_keys:
            f.write(m["uniqueKey"] + "\n")
    with open(artifact_txt, "w", encoding="utf-8") as f:
        for m in matched_keys:
            f.write(m["uniqueKey"] + "\n")
    print(f"Saved txt list to {out_txt}")
else:
    print("Zero matching uniqueKeys found!")
