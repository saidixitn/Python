import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
client = MongoClient(creds["mongo_uri"])
coll = client["jobicarenode_prod"]["Target_P4_Opt"]

doc = coll.find_one({"employerId": "emp-jicn-qrm"}, {
    "uniqueKey": 1,
    "jobId": 1,
    "clientJobId": 1,
    "jobid": 1,
    "jobtitle": 1,
    "location": 1,
    "gpost": 1,
    "job_status": 1,
    "salary_feed": 1,
    "jobdescription_opt": 1
})

for k, v in doc.items():
    if k == "jobdescription_opt":
        print(f"{k}: {repr(v[:100])}")
    else:
        print(f"{k}: {repr(v)}")
