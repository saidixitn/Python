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
c = col.count_documents({
    "employerId": "5f16b7fba780b2085c230ea1",
    "isFromGoogle": True,
    "isBot": False,
    "createdDt": {"$gte": datetime(2024, 8, 1), "$lt": datetime(2024, 9, 1)}
})
print(f"2024-08 Champion count: {c} in {time.time()-t0:.2f}s", flush=True)
