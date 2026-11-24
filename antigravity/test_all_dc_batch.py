import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pymongo import MongoClient
import gspread

load_dotenv()
gc = gspread.service_account(filename="credentials.json")
sh = gc.open_by_key("1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds")
rows = sh.worksheet("Domains").get_all_values()[1:]

mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_db = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])["prod_jobiak_ai"]
dc_db = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])["directclients_prod"]

# Test Direct Apply in 1 single batch query
dc_emps = [r[3].strip() for r in rows if len(r) >= 4 and r[2].strip() == "Direct Apply"]
print(f"Testing {len(dc_emps)} Direct Apply employers in 1 batch...", flush=True)
t0 = time.time()
p_dc = [
    {
        "$match": {
            "employerId": {"$in": dc_emps},
            "isBot": False,
            "browserType": {"$ne": "Unknown"},
            "deviceType": {"$ne": "Unknown"},
            "isFromGoogle": True
        }
    },
    {
        "$group": {
            "_id": {
                "emp": "$employerId",
                "dt": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}}
            },
            "views": {"$sum": 1}
        }
    }
]
res_dc = list(dc_db["userAnalytics"].aggregate(p_dc, allowDiskUse=True))
print(f"Direct Apply batch DONE in {time.time()-t0:.2f}s! Got {len(res_dc)} (emp, day) rows.", flush=True)
