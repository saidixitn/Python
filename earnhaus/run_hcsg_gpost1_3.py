import os
import time
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

t_start = time.time()

# 1. Connect to jobicarenode_prod.Target_P4_Opt
print("[1/3] Querying Target_P4_Opt for gpost in [1, 3]...")
jic_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jic_client = MongoClient(jic_creds["mongo_uri"])
target_col = jic_client["jobicarenode_prod"]["Target_P4_Opt"]

query = {
    "employerId": "emp-jicn-hcsg",
    "job_status": {"$ne": 3},
    "gpost": {"$in": [1, 3]},
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

projection = {
    "uniqueKey": 1,
    "logo": 1,
    "company": 1,
    "clientJobId": 1,
    "jobtitle": 1,
    "location": 1,
    "gpost": 1
}

t0 = time.time()
target_docs = list(target_col.find(query, projection))
print(f"Retrieved {len(target_docs)} documents from Target_P4_Opt in {time.time() - t0:.2f}s.")

# Deduplicate by uniqueKey
unique_jobs = {}
for doc in target_docs:
    uk = doc.get("uniqueKey")
    if uk and uk not in unique_jobs:
        unique_jobs[uk] = doc

target_keys = list(unique_jobs.keys())
print(f"Total Unique Keys: {len(target_keys)}")

# 2. Check posted in prod_jobiak_ai.job
print("\n[2/3] Checking posted status in prod_jobiak_ai.job...")
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

t0 = time.time()
posted_keys = set()
batch_size = 2000
for i in range(0, len(target_keys), batch_size):
    batch = target_keys[i:i+batch_size]
    cursor = job_col.find(
        {
            "employerId": "6a904f26060e8f0b78b0dc81",
            "clientJobId": {"$in": batch},
            "status": "posted"
        },
        {"clientJobId": 1}
    )
    for p in cursor:
        posted_keys.add(p["clientJobId"])

print(f"Found {len(posted_keys)} already POSTED jobs in {time.time() - t0:.2f}s.")

# Filter to NOT posted
not_posted_keys = [k for k in target_keys if k not in posted_keys]
print(f"Jobs NOT posted: {len(not_posted_keys)}")

# 3. Check data_cleansing.ETL_Job_Log
print("\n[3/3] Checking data_cleansing.ETL_Job_Log to exclude existing IDs...")
dc_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "data_cleansing"})
dc_client = MongoClient(dc_creds["mongo_uri"])
etl_log_col = dc_client["data_cleansing"]["ETL_Job_Log"]

t0 = time.time()
present_in_etl = set()
for i in range(0, len(not_posted_keys), batch_size):
    batch = not_posted_keys[i:i+batch_size]
    cursor = etl_log_col.find(
        {
            "employerId": "6a904f26060e8f0b78b0dc81",
            "data.clientJobId": {"$in": batch}
        },
        {"data.clientJobId": 1}
    )
    for e in cursor:
        d = e.get("data", {})
        if "clientJobId" in d:
            present_in_etl.add(d["clientJobId"])

print(f"Found {len(present_in_etl)} unposted jobs present in ETL_Job_Log (these will be excluded) in {time.time() - t0:.2f}s.")

# Exclude those present in ETL_Job_Log
ready_to_post_keys = [k for k in not_posted_keys if k not in present_in_etl]
print(f"\n================ SUMMARY ================")
print(f"Total Matching in Target_P4_Opt (gpost 1 & 3): {len(target_keys)}")
print(f"Already Posted in prod_jobiak_ai.job:          {len(posted_keys)}")
print(f"Not Posted:                                    {len(not_posted_keys)}")
print(f"Present in ETL_Job_Log (excluded):             {len(present_in_etl)}")
print(f"FINAL READY TO POST (NOT in ETL_Job_Log):     {len(ready_to_post_keys)}")
print(f"Total Execution Time:                          {time.time() - t_start:.2f}s")
print(f"=========================================\n")

# Save files
final_records = []
for k in ready_to_post_keys:
    doc = unique_jobs[k]
    final_records.append({
        "uniqueKey": k,
        "clientJobId": doc.get("clientJobId"),
        "jobtitle": doc.get("jobtitle"),
        "location": doc.get("location"),
        "gpost": doc.get("gpost"),
        "company": doc.get("company"),
        "logo": doc.get("logo")
    })

df_final = pd.DataFrame(final_records)

# Save to both latest and standard name with fallback
out_csv_latest = r"c:\Users\JOBIAK\Documents\Python\earnhaus\hcsg_ready_to_post_latest.csv"
df_final.to_csv(out_csv_latest, index=False)
print(f"Saved {len(final_records)} records to {out_csv_latest}")

out_txt_latest = r"c:\Users\JOBIAK\Documents\Python\earnhaus\hcsg_ready_to_post_uniqueKeys_latest.txt"
with open(out_txt_latest, "w") as f:
    f.write("\n".join(ready_to_post_keys))
print(f"Saved uniqueKeys to {out_txt_latest}")

try:
    out_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\hcsg_gpost_1_3_ready_to_post.csv"
    df_final.to_csv(out_csv, index=False)
    print(f"Saved {len(final_records)} records to {out_csv}")
except Exception as e:
    print(f"Could not overwrite {out_csv} (may be open): {e}")

try:
    out_txt = r"c:\Users\JOBIAK\Documents\Python\earnhaus\hcsg_gpost_1_3_uniqueKeys.txt"
    with open(out_txt, "w") as f:
        f.write("\n".join(ready_to_post_keys))
    print(f"Saved uniqueKeys to {out_txt}")
except Exception as e:
    print(f"Could not overwrite {out_txt}: {e}")

# Copy to artifacts directory
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935"
df_final.to_csv(os.path.join(artifact_dir, "hcsg_ready_to_post_latest.csv"), index=False)
with open(os.path.join(artifact_dir, "hcsg_ready_to_post_uniqueKeys_latest.txt"), "w") as f:
    f.write("\n".join(ready_to_post_keys))
try:
    df_final.to_csv(os.path.join(artifact_dir, "hcsg_gpost_1_3_ready_to_post.csv"), index=False)
    with open(os.path.join(artifact_dir, "hcsg_gpost_1_3_uniqueKeys.txt"), "w") as f:
        f.write("\n".join(ready_to_post_keys))
except Exception:
    pass

if ready_to_post_keys:
    print("\nSample Ready to Post IDs (first 25):")
    for r in final_records[:25]:
        print(f"uniqueKey: {r['uniqueKey']} | clientJobId: {r['clientJobId']} | title: {r['jobtitle']} | loc: {r['location']}")
