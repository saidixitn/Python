import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
prod_uri = creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
prod_db = MongoClient(prod_uri)["prod_jobiak_ai"]
col = prod_db["userAnalytics"]

pipeline = [
    {
        "$match": {
            "employerId": "6a7b516d060e8f0b78b0dc5a",
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True
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
res = list(col.aggregate(pipeline, allowDiskUse=True))
print("Monthly aggregation result for 6a7b516d060e8f0b78b0dc5a:")
for r in res:
    print(r)
