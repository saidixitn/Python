import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

sample_jobs = list(job_col.find({"employerId": "6a7b516d060e8f0b78b0dc5a"}, {"jobId": 1, "clientJobId": 1, "location": 1, "title": 1, "status": 1}).limit(10))
for j in sample_jobs:
    print(j)
