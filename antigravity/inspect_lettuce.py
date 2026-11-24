import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
root = MongoClient(mongo_uri)
cred = root["mongo_creds"]["creds"].find_one({"domain": "directclients_prod"})
dc_client = MongoClient(cred["mongo_uri"])
dc_db = dc_client["directclients_prod"]
col = dc_db["Target_P4_Opt"]

print("--- gpost distribution for emp-jbk-lettuce ---")
for r in col.aggregate([
    {"$match": {"employerId": "emp-jbk-lettuce"}},
    {"$group": {"_id": "$gpost", "count": {"$sum": 1}}}
]):
    print(r)

print("\n--- job_status distribution for emp-jbk-lettuce ---")
for r in col.aggregate([
    {"$match": {"employerId": "emp-jbk-lettuce"}},
    {"$group": {"_id": "$job_status", "count": {"$sum": 1}}}
]):
    print(r)

print("\n--- Collections in directclients_prod ---")
cols = dc_db.list_collection_names()
print([c for c in cols if "analytic" in c.lower() or "google" in c.lower() or "log" in c.lower() or "lettuce" in c.lower()])

# Check where userAnalytics is
if "userAnalytics" in cols:
    ua = dc_db["userAnalytics"]
    print("Found userAnalytics in directclients_prod!")
    print("Total UA in directclients_prod:", ua.count_documents({"employerId": "emp-jbk-lettuce"}))
    sample = ua.find_one({"employerId": "emp-jbk-lettuce"})
    print("Sample UA:", sample)
else:
    print("userAnalytics not in directclients_prod")

# Check if analytics is in prod_jobiak_ai
prod_cred = root["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_cred["mongo_uri"])
prod_ua = prod_client["prod_jobiak_ai"]["userAnalytics"]
print("Lettuce UA in prod_jobiak_ai:", prod_ua.count_documents({"employerId": "emp-jbk-lettuce"}))
sample_p = prod_ua.find_one({"employerId": "emp-jbk-lettuce"})
print("Sample prod UA:", sample_p)
