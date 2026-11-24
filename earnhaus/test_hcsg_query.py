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

for name in ["Target_P4_Opt", "emp-hcsg", "newData_emp-jicn-hcsg"]:
    coll = db[name]
    doc = coll.find_one(query)
    print(f"Collection {name}: find_one result = {bool(doc)}")
    if doc:
        print(f"  Sample from {name}: uniqueKey={doc.get('uniqueKey')} clientJobId={doc.get('clientJobId')} jobtitle={doc.get('jobtitle')}")

# What if employerId in emp-hcsg doesn't have "employerId" in query or has different casing?
doc_hcsg = db["emp-hcsg"].find_one()
print("emp-hcsg keys:", list(doc_hcsg.keys()) if doc_hcsg else "empty")
doc_new = db["newData_emp-jicn-hcsg"].find_one()
print("newData_emp-jicn-hcsg keys:", list(doc_new.keys()) if doc_new else "empty")
