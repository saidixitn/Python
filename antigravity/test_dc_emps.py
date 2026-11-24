import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
dc_client = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])
dc_db = dc_client["directclients_prod"]
col = dc_db["userAnalytics"]

for emp in ["emp-jbk-cooperfarms", "emp-jbk-virtahealth", "emp-jbk-lettuce"]:
    c_all = col.count_documents({"employerId": emp})
    c_google = col.count_documents({"employerId": emp, "isFromGoogle": True, "isBot": False})
    print(f"{emp}: all={c_all}, google_human={c_google}", flush=True)
