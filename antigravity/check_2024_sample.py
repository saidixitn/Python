import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]
col = p_db["userAnalytics"]

for emp, name in [("5f16b7fba780b2085c230ea1", "Champion"), ("5e6f1017a780b23e130a1c3b", "Imperial")]:
    d2024 = col.find_one({"employerId": emp, "isFromGoogle": True, "isBot": False, "createdDt": {"$gte": datetime(2024, 1, 1), "$lt": datetime(2025, 1, 1)}})
    d2025 = col.find_one({"employerId": emp, "isFromGoogle": True, "isBot": False, "createdDt": {"$gte": datetime(2025, 1, 1), "$lt": datetime(2026, 1, 1)}})
    print(f"{name} 2024 sample:", d2024.get("createdDt") if d2024 else "None")
    print(f"{name} 2025 sample:", d2025.get("createdDt") if d2025 else "None")
