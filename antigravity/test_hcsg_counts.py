import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
col = db["userAnalytics"]

f1 = {"employerId": emp_id, "isBot": False}
f2 = {
    "employerId": emp_id,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True,
}
f3 = {
    "employerId": emp_id,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
}

print("Filter 1 (isBot: False):", col.count_documents(f1))
print("Filter 2 (Google View Filter: isBot:False, isFromGoogle:True, browserType/deviceType != Unknown):", col.count_documents(f2))
print("Filter 3 (No Bot + browser/device != Unknown):", col.count_documents(f3))

# Check job collection for HCSG
job_col = db["job"]
print("Total jobs for HCSG in job collection:", job_col.count_documents({"employerId": emp_id}))
print("Posted jobs for HCSG in job collection:", job_col.count_documents({"employerId": emp_id, "status": "posted", "isActive": True}))
