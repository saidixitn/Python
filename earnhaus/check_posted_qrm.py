import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# Let's check prod_jobiak_ai.job
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

# Sample check for employerId or clientJobId
sample_job = job_col.find_one({"employerId": "6a7b516d060e8f0b78b0dc5a"}, {"jobId": 1, "clientJobId": 1, "title": 1, "status": 1})
print("Sample prod_jobiak_ai job for QRM:", sample_job)

# Let's check how many total jobs are in prod_jobiak_ai for QRM
qrm_count = job_col.count_documents({"employerId": "6a7b516d060e8f0b78b0dc5a"})
print("Total jobs in prod_jobiak_ai for QRM employerId:", qrm_count)

# Let's also check active/posted jobs
posted_count = job_col.count_documents({"employerId": "6a7b516d060e8f0b78b0dc5a", "status": 1})
print("Posted (status 1) count in prod_jobiak_ai:", posted_count)
