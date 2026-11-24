import os
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
p_db = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"], maxPoolSize=50)["prod_jobiak_ai"]
oldstats = mc["daily_stats"]["oldstats"]
output = mc["daily_stats"]["output"]

proxy_items = [(r[0], r[1], r[3].strip()) for r in rows if len(r) >= 4 and r[2].strip() == "Proxy"]
print(f"Checking {len(proxy_items)} Proxy employers...", flush=True)

cutoff = datetime(2026, 8, 1)

def check_one(item):
    lead, dom, emp = item
    c_old = oldstats.count_documents({"employerId": emp})
    c_out = output.count_documents({"employerId": emp})
    pre = p_db["userAnalytics"].find_one(
        {"employerId": emp, "isFromGoogle": True, "isBot": False, "browserType": {"$ne": "Unknown"}, "deviceType": {"$ne": "Unknown"}, "createdDt": {"$lt": cutoff}},
        {"createdDt": 1}
    )
    return lead, dom, emp, c_old, c_out, pre.get("createdDt") if pre else None

with ThreadPoolExecutor(max_workers=10) as ex:
    for fut in as_completed([ex.submit(check_one, it) for it in proxy_items]):
        lead, dom, emp, c_old, c_out, pre_dt = fut.result()
        print(f"  [{lead}] {dom} ({emp}): oldstats={c_old}, output={c_out}, preAug2026={pre_dt}", flush=True)
