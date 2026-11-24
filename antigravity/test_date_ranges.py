import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]
dc_client = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])
dc_db = dc_client["directclients_prod"]

domains_data = [
    ("qrmhealth", "Proxy", "6a7b516d060e8f0b78b0dc5a"),
    ("champion", "Proxy", "5f16b7fba780b2085c230ea1"),
    ("imperial", "Proxy", "5e6f1017a780b23e130a1c3b"),
    ("cooperfarms", "Direct Apply", "emp-jbk-cooperfarms"),
    ("virtahealth", "Direct Apply", "emp-jbk-virtahealth"),
    ("lettuce", "Direct Apply", "emp-jbk-lettuce"),
    ("yes", "Proxy", "6a86c3d7060e8f0b78b0dc66"),
    ("concentrix", "Proxy", "6a8871d1060e8f0b78b0dc69"),
    ("hcsg", "Proxy", "6a904f26060e8f0b78b0dc81"),
    ("abskids", "Proxy", "6aa8d214060e8f0b78b0dc87"),
    ("suncrest", "Proxy", "6ad8dd02060e8f0b78b0dc9a"),
]

for name, dtype, emp in domains_data:
    col = p_db["userAnalytics"] if dtype == "Proxy" else dc_db["userAnalytics"]
    first = col.find({"employerId": emp, "isFromGoogle": True, "isBot": False}).sort("createdDt", 1).limit(1)
    last = col.find({"employerId": emp, "isFromGoogle": True, "isBot": False}).sort("createdDt", -1).limit(1)
    f_dt = list(first)
    l_dt = list(last)
    f_val = f_dt[0].get("createdDt") if f_dt else None
    l_val = l_dt[0].get("createdDt") if l_dt else None
    print(f"{name} ({emp}): earliest={f_val}, latest={l_val}", flush=True)
