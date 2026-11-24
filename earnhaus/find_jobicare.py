import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# Check all domains in mongo_creds
all_creds = list(local_client["mongo_creds"]["creds"].find({}, {"domain": 1, "mongo_uri": 1}))
print(f"Total domains in mongo_creds: {len(all_creds)}")
for c in all_creds:
    dom = c.get("domain", "")
    if any(k in dom.lower() for k in ["jobicare", "hcsg", "target", "p4", "node"]):
        print(f"Matched domain: {dom}")
