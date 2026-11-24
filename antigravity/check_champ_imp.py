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
    for year in [2023, 2024, 2025]:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        # Using count_documents with employerId
        c = col.count_documents({
            "employerId": emp,
            "isFromGoogle": True,
            "isBot": False,
            "createdDt": {"$gte": start, "$lt": end}
        })
        print(f"{name} ({year}): {c} views", flush=True)
