from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

p4_sample = db["Target_P4_Opt"].find_one({"employerId": "emp-jicn-qrm"})
if p4_sample:
    print("Target_P4_Opt sample:")
    print("  clientJobId:", p4_sample.get("clientJobId"))
    print("  uniqueKey:", p4_sample.get("uniqueKey"))
    print("  job_status:", p4_sample.get("job_status"))
    print("  all keys:", list(p4_sample.keys()))

qrm_sample = db["emp-qrm"].find_one({"employerId": "emp-jicn-qrm"})
if qrm_sample:
    print("\nemp-qrm sample:")
    print("  clientJobId:", qrm_sample.get("clientJobId"))
    print("  uniqueKey:", qrm_sample.get("uniqueKey"))
    print("  job_status:", qrm_sample.get("job_status"))

# Let's check how many unique clientJobIds in emp-qrm and Target_P4_Opt
print("\nSample clientJobIds from emp-qrm:")
for doc in db["emp-qrm"].find({"employerId": "emp-jicn-qrm"}, {"clientJobId": 1, "uniqueKey": 1}).limit(5):
    print(" ", doc.get("clientJobId"), " | uniqueKey:", doc.get("uniqueKey"))
