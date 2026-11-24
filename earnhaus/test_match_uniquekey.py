from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

jicn_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(jicn_creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

sample_jobs = list(job_col.find(
    {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"},
    {"jobId": 1, "clientJobId": 1, "title": 1}
).limit(10))

for sj in sample_jobs:
    cjid = sj.get("clientJobId")
    jid = sj.get("jobId")
    
    # lookup by uniqueKey or clientJobId in Target_P4_Opt
    doc_p4 = db["Target_P4_Opt"].find_one({"employerId": "emp-jicn-qrm", "$or": [{"uniqueKey": cjid}, {"clientJobId": cjid}]})
    doc_qrm = db["emp-qrm"].find_one({"employerId": "emp-jicn-qrm", "$or": [{"uniqueKey": cjid}, {"clientJobId": cjid}]})
    
    status_p4 = doc_p4.get("job_status") if doc_p4 else None
    status_qrm = doc_qrm.get("job_status") if doc_qrm else None
    
    print(f"jobId: {jid} | cjid: {cjid[:30]}...")
    print(f"  Target_P4_Opt: found={bool(doc_p4)}, job_status={status_p4}")
    print(f"  emp-qrm: found={bool(doc_qrm)}, job_status={status_qrm}")
