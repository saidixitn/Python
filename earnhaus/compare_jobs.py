import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

fine_job = job_col.find_one({"jobId": "6adda5d548a2ed0358c4cea9"})
bad_job = job_col.find_one({"jobId": "6adf3a1192132b036d3e9b8d"})

print("=== FINE JOB (Athens, TX - 6adda5d548a2ed0358c4cea9) ===")
if fine_job:
    print("Title:", fine_job.get("title"))
    print("Location:", fine_job.get("location"))
    print("Description (first 800 chars):")
    print(repr(fine_job.get("description", "")[:800]))
    print("\nDescription length:", len(fine_job.get("description", "")))
else:
    print("Not found in DB!")

print("\n" + "="*70 + "\n")

print("=== BAD JOB (Highspire, PA - 6adf3a1192132b036d3e9b8d) ===")
if bad_job:
    print("Title:", bad_job.get("title"))
    print("Location:", bad_job.get("location"))
    print("Description (first 800 chars):")
    print(repr(bad_job.get("description", "")[:800]))
    print("\nDescription length:", len(bad_job.get("description", "")))
else:
    print("Not found in DB!")
