import os
import json
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=8000)

def sanitize(obj, depth=0):
    if depth > 4:
        return "..."
    if isinstance(obj, dict):
        out = {}
        for k, v in list(obj.items())[:25]:
            if k in ("description", "jobDescription", "html", "content", "body") and isinstance(v, str) and len(v) > 120:
                out[k] = v[:120] + "... [TRUNCATED]"
            else:
                out[k] = sanitize(v, depth + 1)
        return out
    elif isinstance(obj, list):
        return [sanitize(x, depth + 1) for x in obj[:3]]
    elif isinstance(obj, datetime):
        return f"ISODate({obj.isoformat()})"
    elif isinstance(obj, ObjectId):
        return f"ObjectId({str(obj)})"
    elif isinstance(obj, str) and len(obj) > 160:
        return obj[:160] + "..."
    return obj

def get_db(db_name):
    cred = client["mongo_creds"]["creds"].find_one({"domain": db_name}, {"mongo_uri": 1})
    if cred and cred.get("mongo_uri"):
        return MongoClient(cred["mongo_uri"], serverSelectionTimeoutMS=8000)[db_name]
    return client[db_name]

targets = [
    ("daily_stats", "input"),
    ("daily_stats", "output"),
    ("daily_stats", "oldstats"),
    ("daily_domain_stats", "stats"),
    ("domain_expires", "domains"),
    ("domain_expires", "semrush_url's"),
    ("domain_postings", "domains"),
    ("xml_timings", "feed_timings"),
    ("xml_timings", "feed_timings_history"),
    ("banana_analytics", "stats"),
    ("GenAI", "faq"),
    ("prod_jobiak_ai", "job"),
    ("prod_jobiak_ai", "userAnalytics"),
    ("prod_jobiak_ai", "jobsGoogleSubmittedLog"),
    ("directclients_prod", "Target_P4_Opt"),
    ("directclients_prod", "userAnalytics"),
    ("directclients_prod", "aj_jp_google_logs"),
    ("directclients_prod", "alternative_desc_change"),
    ("ETL_Scrapping_Data", "ETL_Scraping_Data"),
    ("data_cleansing", "ETL_AUD_Data"),
    ("hextill_prod", "Target_P4_Opt"),
    ("v2valuejobs_prod", "static_keywords"),
    ("generateXml_prod", "emp-gxc-albertsons"),
]

results = {}
for db_name, col_name in targets:
    key = f"{db_name}.{col_name}"
    try:
        db = get_db(db_name)
        col = db.get_collection(col_name)
        doc = col.find_one({})
        indexes = {}
        try:
            for idx_name, idx_info in col.index_information().items():
                indexes[idx_name] = idx_info.get("key")
        except Exception as ie:
            indexes = {"error": str(ie)}
        results[key] = {
            "sample_doc": sanitize(doc) if doc else None,
            "indexes": indexes
        }
        print(f"OK: {key} (indexes: {len(indexes)})")
    except Exception as e:
        results[key] = {"error": str(e)}
        print(f"ERR: {key} -> {e}")

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\live_schemas_and_indexes.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str)

print("Done!")
