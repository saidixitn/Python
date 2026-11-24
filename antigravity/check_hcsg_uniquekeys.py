import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))

# Connect to jobicarenode_prod
rec_jicn = client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
if not rec_jicn:
    print("jobicarenode_prod creds not found!")
    sys.exit(1)

jicn_client = MongoClient(rec_jicn["mongo_uri"], serverSelectionTimeoutMS=8000)
db_jicn = jicn_client["jobicarenode_prod"]

# Connect to prod_jobiak_ai
rec_pj = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
pj_client = MongoClient(rec_pj["mongo_uri"], serverSelectionTimeoutMS=8000)
db_pj = pj_client["prod_jobiak_ai"]

print("Connected to both databases.")

# Check sample HCSG in prod_jobiak_ai
hcsg_emp_id = "6a904f26060e8f0b78b0dc81"
sample_pj = db_pj.job.find_one({"employerId": hcsg_emp_id})
print("Sample HCSG job in prod_jobiak_ai:")
if sample_pj:
    print(f"  jobId: {sample_pj.get('jobId')}")
    print(f"  clientJobId: {sample_pj.get('clientJobId')}")
    print(f"  uniqueKey: {sample_pj.get('uniqueKey')}")
    print(f"  title: {sample_pj.get('title')}")
    print(f"  status: {sample_pj.get('status')}, isActive: {sample_pj.get('isActive')}")

# Query jobicarenode_prod
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

cursor_jicn = db_jicn.Target_P4_Opt.find(query_jicn, {"uniqueKey": 1, "jobtitle": 1, "uncleanedLocation": 1, "gpost": 1, "job_status": 1})
jicn_jobs = list(cursor_jicn)
print(f"\nTotal jobs found in jobicarenode_prod matching query: {len(jicn_jobs)}")

uniquekeys = [j["uniqueKey"] for j in jicn_jobs if j.get("uniqueKey")]
print(f"Total uniqueKeys extracted: {len(uniquekeys)} (unique: {len(set(uniquekeys))})")
if uniquekeys:
    print("Sample uniqueKeys from jobicare:", uniquekeys[:3])
