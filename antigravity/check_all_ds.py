import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
ds = mc["daily_stats"]
print("daily_stats collections:", ds.list_collection_names())
for c in ds.list_collection_names():
    doc = ds[c].find_one()
    print(f"Collection {c}: count={ds[c].count_documents({})}, sample keys: {list(doc.keys()) if doc else 'empty'}")
    if doc and "Date" in doc:
        min_d = ds[c].find_one(sort=[("Date", 1)])
        max_d = ds[c].find_one(sort=[("Date", -1)])
        print(f"  Date range: {min_d.get('Date')} to {max_d.get('Date')}")
