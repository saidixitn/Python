import os
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import Counter

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds_col = primary_client["mongo_creds"]["creds"]

prod_uri = creds_col.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
jicn_uri = creds_col.find_one({"domain": "jobicarenode_prod"})["mongo_uri"]

prod_db = MongoClient(prod_uri)["prod_jobiak_ai"]
jicn_db = MongoClient(jicn_uri)["jobicarenode_prod"]

qrm_prod_id = "6a7b516d060e8f0b78b0dc5a"
qrm_jicn_id = "emp-jicn-qrm"

print("--- 1. JOBICARE (jobicarenode_prod.Target_P4_Opt) ---")
jicn_col = jicn_db["Target_P4_Opt"]

# Total in Target_P4_Opt
total_jicn = jicn_col.count_documents({"employerId": qrm_jicn_id})
print(f"Total QRM docs in Target_P4_Opt: {total_jicn}")

# By job_status
status_counts = jicn_col.aggregate([
    {"$match": {"employerId": qrm_jicn_id}},
    {"$group": {"_id": "$job_status", "count": {"$sum": 1}}}
])
print("By job_status:", list(status_counts))

# By extraInfo.feedData (all)
feed_data_all = jicn_col.aggregate([
    {"$match": {"employerId": qrm_jicn_id}},
    {"$group": {"_id": "$extraInfo.feedData", "count": {"$sum": 1}}}
])
print("By extraInfo.feedData (all):", list(feed_data_all))

# By extraInfo.feedData (active / job_status != 3)
feed_data_active = jicn_col.aggregate([
    {"$match": {"employerId": qrm_jicn_id, "job_status": {"$ne": 3}}},
    {"$group": {"_id": "$extraInfo.feedData", "count": {"$sum": 1}}}
])
print("By extraInfo.feedData (active, job_status != 3):", list(feed_data_active))

# By gpost
gpost_counts = jicn_col.aggregate([
    {"$match": {"employerId": qrm_jicn_id}},
    {"$group": {"_id": "$gpost", "count": {"$sum": 1}}}
])
print("By gpost:", list(gpost_counts))

print("\n--- 2. PRODUCTION (prod_jobiak_ai.job) ---")
prod_col = prod_db["job"]

total_prod = prod_col.count_documents({"employerId": qrm_prod_id})
print(f"Total QRM docs in prod_jobiak_ai.job: {total_prod}")

prod_status = prod_col.aggregate([
    {"$match": {"employerId": qrm_prod_id}},
    {"$group": {"_id": {"status": "$status", "isActive": "$isActive"}, "count": {"$sum": 1}}}
])
print("Production status & isActive:", list(prod_status))

# Check feedData / expansion in production directly if available
prod_expansion = prod_col.aggregate([
    {"$match": {"employerId": qrm_prod_id, "status": "posted", "isActive": True}},
    {"$group": {"_id": {"isLocationExpanded": "$isLocationExpanded", "isTitleExpanded": "$isTitleExpanded"}, "count": {"$sum": 1}}}
])
print("Production posted jobs expansion flags:", list(prod_expansion))
