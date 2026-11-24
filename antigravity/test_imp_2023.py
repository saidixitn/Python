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

t0 = time.time()
pipeline = [
    {
        "$match": {
            "employerId": "5e6f1017a780b23e130a1c3b",
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True,
            "createdDt": {"$gte": datetime(2023, 1, 1), "$lt": datetime(2024, 1, 1)}
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
res = list(col.aggregate(pipeline, allowDiskUse=True))
print(f"Imperial 2023 done in {time.time()-t0:.2f}s:", res, flush=True)
