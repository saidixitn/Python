import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]
col = p_db["userAnalytics"]

proxy_emps = [
    ("qrmhealth", "6a7b516d060e8f0b78b0dc5a"),
    ("champion", "5f16b7fba780b2085c230ea1"),
    ("imperial", "5e6f1017a780b23e130a1c3b"),
    ("yes", "6a86c3d7060e8f0b78b0dc66"),
    ("concentrix", "6a8871d1060e8f0b78b0dc69"),
    ("hcsg", "6a904f26060e8f0b78b0dc81"),
    ("abskids", "6aa8d214060e8f0b78b0dc87"),
    ("suncrest", "6ad8dd02060e8f0b78b0dc9a"),
]

cutoff = datetime(2026, 8, 1, 0, 0, 0)
for name, emp in proxy_emps:
    # Use index on createdDt_1
    doc = col.find_one({
        "employerId": emp,
        "isFromGoogle": True,
        "isBot": False,
        "createdDt": {"$lt": cutoff}
    })
    print(f"{name} ({emp}) has traffic before 2026-08-01? {'YES: ' + str(doc.get('createdDt')) if doc else 'NO'}", flush=True)
