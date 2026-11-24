import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
col = db["userAnalytics"]

null_child = col.count_documents({"employerId": emp_id, "isBot": False, "childJobId": None})
null_jobid = col.count_documents({"employerId": emp_id, "isBot": False, "jobId": None})
diff = col.count_documents({"employerId": emp_id, "isBot": False, "$expr": {"$ne": ["$jobId", "$childJobId"]}})

print("Null childJobId:", null_child)
print("Null jobId:", null_jobid)
print("jobId != childJobId:", diff)
