import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

clients = [
    ("YES! Communities", "6a86c3d7060e8f0b78b0dc66"),
    ("QRM", "6a7b516d060e8f0b78b0dc5a")
]

for name, emp_id in clients:
    total_jobs = db["job"].count_documents({"employerId": emp_id})
    posted_jobs = db["job"].count_documents({"employerId": emp_id, "status": "posted", "isActive": True})
    
    # Check analytics
    sample_ua = db["userAnalytics"].find_one({"employerId": emp_id})
    gviews = db["userAnalytics"].count_documents({
        "employerId": emp_id,
        "isBot": False,
        "browserType": {"$ne": "Unknown"},
        "deviceType": {"$ne": "Unknown"},
        "isFromGoogle": True
    })
    bots = db["userAnalytics"].count_documents({"employerId": emp_id, "isBot": True})
    
    print(f"=== {name} ({emp_id}) ===")
    print(f"Total jobs: {total_jobs}, Posted active jobs: {posted_jobs}")
    print(f"Google views (isFromGoogle: True): {gviews}, Bot visits: {bots}")
    if sample_ua:
        print("Sample UA childJobId:", sample_ua.get("childJobId"), "jobId:", sample_ua.get("jobId"))
