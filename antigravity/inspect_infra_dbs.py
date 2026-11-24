import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=5000)

# List non-generic infrastructure / special DBs in mongo_creds.creds
infra_dbs = list(client["mongo_creds"]["creds"].find(
    {"$or": [
        {"active": False},
        {"domain": {"$in": ["prod_jobiak_ai", "directclients_prod", "generateXml_prod", "ETL_Scrapping_Data", "data_cleansing", "alljobs_prod", "surveys_prod", "jobicarenode_prod", "dc_prod"]}}
    ]},
    {"_id": 0, "domain": 1, "ip": 1, "active": 1}
))
print("=== INFRASTRUCTURE & CORE DBS ===")
for d in sorted(infra_dbs, key=lambda x: str(x.get("domain", ""))):
    print(f"  {d.get('domain')} | IP: {d.get('ip')} | active: {d.get('active')}")

# Also list all DBs on the central local/remote server (<CENTRAL_VPS_IP>)
print("\n=== CENTRAL VPS MONGO DATABASES (<CENTRAL_VPS_IP>) ===")
for db_name in sorted(client.list_database_names()):
    if db_name not in ["admin", "local", "config"]:
        cols = sorted(client[db_name].list_collection_names())
        print(f"  {db_name}: {cols[:15]}{' ...' if len(cols)>15 else ''}")
