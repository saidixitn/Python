import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

sample_ids = ["6ae9c44f855f8c0394f3f90c", "6adf3a1192132b036d3e9b8d"]

for jid in sample_ids:
    j = job_col.find_one({"jobId": jid})
    desc = j.get("description", "")
    print(f"=== JobId: {jid} ===")
    # find all lines or tags
    for line in desc.split("<"):
        if "strong" in line.lower():
            print("<" + line)
