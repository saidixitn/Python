import os
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import Counter

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
col = db["userAnalytics"]

sample_docs = list(col.find({"employerId": emp_id, "isBot": False}).limit(5))
for i, d in enumerate(sample_docs):
    print(f"--- Doc {i} ---")
    for k in ["jobId", "childJobId", "jobPubJobId", "jobtitle", "title", "location", "isFromGoogle", "browserType", "deviceType", "createdDt", "viewDate"]:
        print(f"  {k}: {d.get(k)}")

# Also check how many have jobtitle or location directly in userAnalytics
has_jobtitle = col.count_documents({"employerId": emp_id, "isBot": False, "jobtitle": {"$exists": True, "$ne": ""}})
has_location = col.count_documents({"employerId": emp_id, "isBot": False, "location": {"$exists": True, "$ne": ""}})
print(f"\nDirect jobtitle in userAnalytics: {has_jobtitle} / 41110")
print(f"Direct location in userAnalytics: {has_location} / 41110")
