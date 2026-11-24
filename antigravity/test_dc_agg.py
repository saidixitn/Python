import os
import time
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
dc_client = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])
dc_db = dc_client["directclients_prod"]
col = dc_db["userAnalytics"]

for emp in ["emp-jbk-cooperfarms", "emp-jbk-virtahealth"]:
    t0 = time.time()
    pipeline = [
        {
            "$match": {
                "employerId": emp,
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
    res = list(col.aggregate(pipeline, allowDiskUse=True))
    print(f"{emp}: {len(res)} days, total={sum(r['views'] for r in res)}, time={time.time()-t0:.2f}s", flush=True)
    if res:
        print(f"  first: {res[0]}, last: {res[-1]}")
