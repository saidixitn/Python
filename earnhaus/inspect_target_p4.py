import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
client = MongoClient(creds["mongo_uri"])
coll = client["jobicarenode_prod"]["Target_P4_Opt"]

doc = coll.find_one({"employerId": "emp-jicn-qrm"})
if doc:
    print("Found doc! Keys:")
    for k in doc.keys():
        v = doc[k]
        val_str = str(v)[:80] if not isinstance(v, (dict, list)) else f"{type(v)} (len {len(v)})"
        print(f"  {k}: {val_str}")
else:
    print("No doc found with employerId emp-jicn-qrm")
