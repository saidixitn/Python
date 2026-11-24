import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# prod_jobiak_ai
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

# jobicarenode_prod
jicn_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(jicn_creds["mongo_uri"])
jicn_db = jicn_client["jobicarenode_prod"]

sample_jobs = list(job_col.find(
    {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"},
    {"jobId": 1, "clientJobId": 1, "title": 1}
).limit(5))

print("Sample posted jobs in prod_jobiak_ai:")
for sj in sample_jobs:
    cjid = sj.get("clientJobId")
    jid = sj.get("jobId")
    print(f"jobId: {jid}, clientJobId: {cjid}")
    
    # Check in Target_P4_Opt
    doc_target = jicn_db["Target_P4_Opt"].find_one({"employerId": "emp-jicn-qrm", "clientJobId": cjid})
    # Check in emp-qrm
    doc_qrm = jicn_db["emp-qrm"].find_one({"employerId": "emp-jicn-qrm", "clientJobId": cjid})
    
    print(f"  In Target_P4_Opt: found={bool(doc_target)}, job_status={doc_target.get('job_status') if doc_target else None}")
    print(f"  In emp-qrm: found={bool(doc_qrm)}, job_status={doc_qrm.get('job_status') if doc_qrm else None}")
