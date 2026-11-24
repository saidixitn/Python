import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
jic_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jic_client = MongoClient(jic_creds["mongo_uri"])
db = jic_client["jobicarenode_prod"]

query = {
    "employerId": "emp-jicn-hcsg",
    "job_status": {"$ne": 3},
    "gpost": 1,
    "jobtitle": {"$in": ["Dietary Aide", "Registered Dietitian", "Laundry Worker", "Cook", "Housekeeper"]}
}

for coll_name in db.list_collection_names():
    cnt = db[coll_name].count_documents(query)
    if cnt > 0:
        print(f"Collection '{coll_name}' MATCHES query! Count: {cnt}")
