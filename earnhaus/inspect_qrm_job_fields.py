import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

sample = job_col.find_one({"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"})
print("Keys in posted QRM job:")
for k in sample.keys():
    v = sample[k]
    val_str = str(v)[:80] if not isinstance(v, (dict, list)) else f"{type(v)} (len {len(v)})"
    print(f"  {k}: {val_str}")
