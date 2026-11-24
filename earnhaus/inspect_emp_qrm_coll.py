from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

emp_qrm = db["emp-qrm"]
print("emp-qrm count:", emp_qrm.estimated_document_count())
sample_qrm = emp_qrm.find_one()
if sample_qrm:
    print("Sample emp-qrm keys:", list(sample_qrm.keys()))
    print("Sample employerId in emp-qrm:", sample_qrm.get("employerId"))
    print("Sample jobtitle:", sample_qrm.get("jobtitle") or sample_qrm.get("title"))
    print("Sample description preview:", (sample_qrm.get("description") or sample_qrm.get("job_description") or "")[:300])

# Also check Target_P4_Opt
p4 = db["Target_P4_Opt"]
print("\nTarget_P4_Opt estimated count:", p4.estimated_document_count())
sample_target = p4.find_one({"employerId": sample_qrm.get("employerId")}) if sample_qrm else None
if not sample_target:
    # Try finding with employerId == 'emp-jicn-qrm' or 'emp-qrm'
    sample_target = p4.find_one({"employerId": "emp-jicn-qrm"})
    if not sample_target:
        sample_target = p4.find_one({"employerId": "emp-qrm"})
print("Sample target found:", bool(sample_target))
if sample_target:
    print("Sample target employerId:", sample_target.get("employerId"))
    print("Sample target description preview:", (sample_target.get("description") or sample_target.get("job_description") or "")[:300])
