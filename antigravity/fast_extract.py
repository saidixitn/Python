import os
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import defaultdict

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
oldstats = mc["daily_stats"]["oldstats"]
output = mc["daily_stats"]["output"]

creds = mc["mongo_creds"]["creds"]
dc_client = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])
dc_db = dc_client["directclients_prod"]

domains_data = [
    {"domain": "qrmhealth.com/gfj/", "type": "Proxy", "employerId": "6a7b516d060e8f0b78b0dc5a", "client": "Quality Rehab Management (QRM)"},
    {"domain": "championwindow.com/gfj/", "type": "Proxy", "employerId": "5f16b7fba780b2085c230ea1", "client": "Champion Window"},
    {"domain": "imperialsupplies.com/jobiak", "type": "Proxy", "employerId": "5e6f1017a780b23e130a1c3b", "client": "Imperial Supplies"},
    {"domain": "gfj.cooperfarms.com/", "type": "Direct Apply", "employerId": "emp-jbk-cooperfarms", "client": "Cooper Farms"},
    {"domain": "gfj.virtahealth.com/", "type": "Direct Apply", "employerId": "emp-jbk-virtahealth", "client": "Virta Health"},
    {"domain": "gfj.lettuce.com", "type": "Direct Apply", "employerId": "emp-jbk-lettuce", "client": "Lettuce Entertain You"},
    {"domain": "yescommunities.com/gfj/", "type": "Proxy", "employerId": "6a86c3d7060e8f0b78b0dc66", "client": "YES! Communities"},
    {"domain": "concentrix.com/gfj/", "type": "Proxy", "employerId": "6a8871d1060e8f0b78b0dc69", "client": "Concentrix"},
    {"domain": "hcsgcorp.com/gfj/", "type": "Proxy", "employerId": "6a904f26060e8f0b78b0dc81", "client": "Healthcare Services Group (HCSG)"},
    {"domain": "abskids.com/gfj/", "type": "Proxy", "employerId": "6aa8d214060e8f0b78b0dc87", "client": "ABS Kids"},
    {"domain": "suncrestcare.com/gfj/", "type": "Proxy", "employerId": "6ad8dd02060e8f0b78b0dc9a", "client": "Suncrest Care"},
]

# 1. Fetch from daily_stats (oldstats + output)
daily_views = defaultdict(dict)  # emp_id -> {date_str: views}

for item in domains_data:
    emp = item["employerId"]
    # oldstats
    for doc in oldstats.find({"employerId": emp}):
        dt = doc.get("Date")
        if dt:
            d_str = dt.strftime("%Y-%m-%d")
            daily_views[emp][d_str] = doc.get("DB_Clicks", 0)
    
    # output (overrides or adds later dates)
    for doc in output.find({"employerId": emp}):
        dt = doc.get("Date")
        if dt:
            d_str = dt.strftime("%Y-%m-%d")
            # If closed window (DB_Clicks present)
            if "DB_Clicks" in doc:
                daily_views[emp][d_str] = doc.get("DB_Clicks", 0)

# For Cooper Farms & Virta Health (not in oldstats), fetch from directclients_prod.userAnalytics
for emp in ["emp-jbk-cooperfarms", "emp-jbk-virtahealth"]:
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
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdDt"}},
                "views": {"$sum": 1}
            }
        }
    ]
    for r in dc_db["userAnalytics"].aggregate(pipeline, allowDiskUse=True):
        if r.get("_id"):
            daily_views[emp][r["_id"]] = r["views"]

print("=== STATS EXTRACTED ===")
for item in domains_data:
    emp = item["employerId"]
    dates = daily_views[emp]
    total_v = sum(dates.values())
    max_d = max(dates.items(), key=lambda x: x[1]) if dates else ("None", 0)
    yest_v = dates.get("2026-11-11", 0)
    print(f"{item['client']} ({item['domain']}): Total Days={len(dates)}, Total Views={total_v}, Max={max_d[1]} on {max_d[0]}, Yesterday (2026-11-11)={yest_v}")
