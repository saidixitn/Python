import os
import time
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]
col = p_db["userAnalytics"]

# Test aggregating by year for Champion Window
for year in [2023, 2024, 2025, 2026]:
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    t0 = time.time()
    pipeline = [
        {
            "$match": {
                "employerId": "5f16b7fba780b2085c230ea1",
                "isBot": False,
                "browserType": {"$ne": "Unknown"},
                "deviceType": {"$ne": "Unknown"},
                "isFromGoogle": True,
                "createdDt": {"$gte": start, "$lt": end}
            }
        },
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$createdDt"},
                    "month": {"$month": "$createdDt"}
                },
                "views": {"$sum": 1}
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]
    res = list(col.aggregate(pipeline, allowDiskUse=True, hint="createdDt_1"))
    print(f"Champion {year}: {res} in {time.time()-t0:.2f}s", flush=True)
