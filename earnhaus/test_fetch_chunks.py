import os
import time
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

query = {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"}
projection = {"jobId": 1, "submittedUrl": 1, "description": 1, "title": 1, "location": 1}

print("Fetching all posted QRM jobs in batches...")
all_jobs = []
last_id = None

while True:
    q = dict(query)
    if last_id:
        q["_id"] = {"$gt": last_id}
    
    batch = list(job_col.find(q, projection).sort("_id", 1).limit(500))
    if not batch:
        break
    all_jobs.extend(batch)
    last_id = batch[-1]["_id"]
    print(f"Fetched {len(all_jobs)} jobs...")

print(f"Total posted QRM jobs fetched: {len(all_jobs)}")
