import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]

p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]
col = p_db["userAnalytics"]

pipeline = [
    {
        "$match": {
            "employerId": "5f16b7fba780b2085c230ea1",
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True
        }
    },
    {
        "$group": {
            "_id": {
                "$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}
            },
            "views": {"$sum": 1}
        }
    },
    {"$sort": {"_id": 1}}
]

t0 = time.time()
print("Running aggregation with hint='employerId_1'...", flush=True)
res = list(col.aggregate(pipeline, allowDiskUse=True, hint="employerId_1"))
print(f"Done in {time.time() - t0:.2f}s, days count: {len(res)}, total views: {sum(r['views'] for r in res)}")
for r in res[:5]:
    print(" ", r)
