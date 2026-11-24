import os
import time
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
col = p_client["prod_jobiak_ai"]["userAnalytics"]

pipeline = [
    {
        "$match": {
            "employerId": "5f16b7fba780b2085c230ea1",
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True,
            "createdDt": {"$gte": datetime(2024, 1, 1), "$lt": datetime(2026, 8, 1)}
        }
    },
    {
        "$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$createdDt"}},
            "views": {"$sum": 1}
        }
    },
    {"$sort": {"_id": 1}}
]

t0 = time.time()
print("Starting aggregation for 2024-2026 prior to Aug...", flush=True)
res = list(col.aggregate(pipeline, allowDiskUse=True))
print(f"Finished in {time.time()-t0:.2f}s, months count={len(res)}:")
for r in res:
    print(" ", r["_id"], ":", r["views"])
