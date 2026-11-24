from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

print("Collections in jobicarenode_prod:")
for c in db.list_collection_names():
    if "target" in c.lower() or "qrm" in c.lower() or "opt" in c.lower() or "job" in c.lower():
        print(" ", c)

# Check Target_P4_Opt for QRM
p4 = db["Target_P4_Opt"]
print("\nChecking Target_P4_Opt for emp-qrm:")
qrm_docs = list(p4.find({"employerId": {"$regex": "qrm", "$options": "i"}}, {"employerId": 1}).limit(5))
print("Target_P4_Opt matching qrm:", qrm_docs)

# What are all employerIds matching qrm or emp-qrm?
eids = p4.distinct("employerId", {"employerId": {"$regex": "qrm", "$options": "i"}})
print("Distinct employerIds with 'qrm' in Target_P4_Opt:", eids)

# Check count for emp-qrm
cnt = p4.count_documents({"employerId": "emp-qrm"})
print("Count for employerId == 'emp-qrm':", cnt)

# Check count for emp-jicn-qrm
cnt2 = p4.count_documents({"employerId": "emp-jicn-qrm"})
print("Count for employerId == 'emp-jicn-qrm':", cnt2)
