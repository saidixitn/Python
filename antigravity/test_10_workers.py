import os
import time
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]

p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]

dc_client = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])
dc_db = dc_client["directclients_prod"]

domains_data = [
    {"domain": "qrmhealth.com/gfj/", "type": "Proxy", "employerId": "6a7b516d060e8f0b78b0dc5a"},
    {"domain": "championwindow.com/gfj/", "type": "Proxy", "employerId": "5f16b7fba780b2085c230ea1"},
    {"domain": "imperialsupplies.com/jobiak", "type": "Proxy", "employerId": "5e6f1017a780b23e130a1c3b"},
    {"domain": "gfj.cooperfarms.com/", "type": "Direct Apply", "employerId": "emp-jbk-cooperfarms"},
    {"domain": "gfj.virtahealth.com/", "type": "Direct Apply", "employerId": "emp-jbk-virtahealth"},
    {"domain": "gfj.lettuce.com", "type": "Direct Apply", "employerId": "emp-jbk-lettuce"},
    {"domain": "yescommunities.com/gfj/", "type": "Proxy", "employerId": "6a86c3d7060e8f0b78b0dc66"},
    {"domain": "concentrix.com/gfj/", "type": "Proxy", "employerId": "6a8871d1060e8f0b78b0dc69"},
    {"domain": "hcsgcorp.com/gfj/", "type": "Proxy", "employerId": "6a904f26060e8f0b78b0dc81"},
    {"domain": "abskids.com/gfj/", "type": "Proxy", "employerId": "6aa8d214060e8f0b78b0dc87"},
    {"domain": "suncrestcare.com/gfj/", "type": "Proxy", "employerId": "6ad8dd02060e8f0b78b0dc9a"},
]

def fetch_domain(item):
    emp_id = item["employerId"]
    dtype = item["type"]
    dom = item["domain"]
    
    col = p_db["userAnalytics"] if dtype == "Proxy" else dc_db["userAnalytics"]
    
    # Match standard Google pure human views
    match_filter = {
        "employerId": emp_id,
        "isBot": False,
        "browserType": {"$ne": "Unknown"},
        "deviceType": {"$ne": "Unknown"},
        "isFromGoogle": True
    }
    
    t0 = time.time()
    # Daily aggregation pipeline
    pipeline = [
        {"$match": match_filter},
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
    
    results = list(col.aggregate(pipeline, allowDiskUse=True))
    elapsed = time.time() - t0
    total_views = sum(r["views"] for r in results)
    days_count = len(results)
    
    return {
        "domain": dom,
        "employerId": emp_id,
        "type": dtype,
        "days_count": days_count,
        "total_views": total_views,
        "sample": results[:3],
        "elapsed": round(elapsed, 2)
    }

print("Running test across 11 domains with 10 workers...")
start_all = time.time()
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_domain, item) for item in domains_data]
    for fut in as_completed(futures):
        res = fut.result()
        print(f"[{res['domain']}] Views: {res['total_views']}, Days: {res['days_count']}, Took: {res['elapsed']}s")

print(f"ALL DONE in {round(time.time() - start_all, 2)}s")
