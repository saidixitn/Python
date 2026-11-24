import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(r"./.env")
root = MongoClient(os.getenv("MONGO_URI"))
creds = root["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
db = MongoClient(creds["mongo_uri"])["prod_jobiak_ai"]

for name, emp_id in [("QRM", "6a7b516d060e8f0b78b0dc5a"), ("ABS Kids", "6aa8d214060e8f0b78b0dc87")]:
    doc = db.userAnalytics.find_one({"employerId": emp_id, "isFromGoogle": True, "isBot": False})
    print(f"=== SAMPLE CLICK FOR {name} ===")
    if doc:
        # print keys and interesting values
        print(json.dumps(doc, indent=2, default=str))
    else:
        print("No click document found")

    # Check jobId vs childJobId in clicks
    jobId_count = db.userAnalytics.count_documents({"employerId": emp_id, "isFromGoogle": True, "isBot": False, "jobId": {"$exists": True, "$ne": None}})
    childJobId_count = db.userAnalytics.count_documents({"employerId": emp_id, "isFromGoogle": True, "isBot": False, "childJobId": {"$exists": True, "$ne": None}})
    print(f"{name} counts: jobId={jobId_count}, childJobId={childJobId_count}")
