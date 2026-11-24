import os
import time
from datetime import datetime
import json
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
            "employerId": "5e6f1017a780b23e130a1c3b",
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
print("Starting aggregation for Imperial Supplies (2024-01-01 to 2026-08-01)...", flush=True)
res = list(col.aggregate(pipeline, allowDiskUse=True))
print(f"Finished aggregation in {time.time()-t0:.2f}s")

output_data = {r["_id"]: r["views"] for r in res}
output_list = [{"month": r["_id"], "views": r["views"]} for r in res]

out_path = r"c:\Users\JOBIAK\Documents\Python\antigravity\imperial_2024_2025.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"Wrote output to {out_path}:")
print(json.dumps(output_data, indent=2))
