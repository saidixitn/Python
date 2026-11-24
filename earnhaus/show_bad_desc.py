import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

bad_job = job_col.find_one({"jobId": "6adf3a1192132b036d3e9b8d"})
desc = bad_job.get("description", "")
print("Full Description of 6adf3a1192132b036d3e9b8d:")
print(desc)
print("\nCount <strong:", desc.count("<strong"))
print("Count </strong:", desc.count("</strong"))
print("Difference:", desc.count("<strong") - desc.count("</strong"))
