import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
import json
from bson import json_util

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
rec = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
if not rec:
    print("Error: prod_jobiak_ai creds not found!")
    sys.exit(1)

pj_client = MongoClient(rec["mongo_uri"], serverSelectionTimeoutMS=8000)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

print("Listing matching collections in prod_jobiak_ai...")
cols = db.list_collection_names()
kw_cols = [c for c in cols if any(k in c.lower() for k in ["keyword", "rula", "rule"])]
print("Matching collections:", kw_cols)

print("\n" + "="*60)
print("1. INSPECTING rula_location_keywords")
print("="*60)
if "rula_location_keywords" in cols:
    col = db["rula_location_keywords"]
    print("Indexes on rula_location_keywords:", col.index_information())
    
    # Check by employerId
    docs_by_emp = list(col.find({"employerId": emp_id}))
    print(f"Docs found by employerId '{emp_id}': {len(docs_by_emp)}")
    
    # If none, search by company name or regex
    if not docs_by_emp:
        print("Searching by company/name regex...")
        docs_by_name = list(col.find({"$or": [
            {"company": {"$regex": "yes", "$options": "i"}},
            {"companyName": {"$regex": "yes", "$options": "i"}},
            {"employerName": {"$regex": "yes", "$options": "i"}},
            {"domain": {"$regex": "yescommunities", "$options": "i"}}
        ]}))
        print(f"Docs found by name search: {len(docs_by_name)}")
        sample_docs = docs_by_name[:3]
    else:
        sample_docs = docs_by_emp[:3]
        
    for i, d in enumerate(sample_docs):
        print(f"\n--- Sample {i+1} in rula_location_keywords ---")
        print(json_util.dumps(d, indent=2))
else:
    print("rula_location_keywords not found! Checking similar...")

print("\n" + "="*60)
print("2. INSPECTING jobiak_keyword_Updation")
print("="*60)
if "jobiak_keyword_Updation" in cols:
    col = db["jobiak_keyword_Updation"]
    print("Indexes on jobiak_keyword_Updation:", col.index_information())
    
    docs_by_emp = list(col.find({"employerId": emp_id}))
    print(f"Docs found by employerId '{emp_id}': {len(docs_by_emp)}")
    
    if not docs_by_emp:
        print("Searching by company/name regex...")
        docs_by_name = list(col.find({"$or": [
            {"company": {"$regex": "yes", "$options": "i"}},
            {"companyName": {"$regex": "yes", "$options": "i"}},
            {"employerName": {"$regex": "yes", "$options": "i"}},
            {"domain": {"$regex": "yescommunities", "$options": "i"}}
        ]}))
        print(f"Docs found by name search: {len(docs_by_name)}")
        sample_docs = docs_by_name[:3]
    else:
        sample_docs = docs_by_emp[:3]
        
    for i, d in enumerate(sample_docs):
        print(f"\n--- Sample {i+1} in jobiak_keyword_Updation ---")
        print(json_util.dumps(d, indent=2))
else:
    print("jobiak_keyword_Updation not found!")
