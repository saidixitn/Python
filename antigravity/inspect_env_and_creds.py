import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
print("=== .ENV KEYS ===")
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                # Mask password part of URI if present
                host_part = v.split("@")[-1] if "@" in v else "(local/other)"
                print(f"  {k} -> host: {host_part}")

uri = os.getenv("MONGO_URI")
if uri:
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        creds = list(client["mongo_creds"]["creds"].find({}, {"_id": 0, "domain": 1, "ip": 1, "active": 1}))
        print(f"\n=== mongo_creds.creds ({len(creds)} domains) ===")
        for c in sorted(creds, key=lambda x: str(x.get("domain", ""))):
            print(f"  {c.get('domain')} | IP: {c.get('ip')} | active: {c.get('active')}")
        
        ds_inputs = list(client["daily_stats"]["input"].find({}, {"_id": 0, "Domain": 1, "DomainType": 1, "Company": 1, "employerId": 1}))
        print(f"\n=== daily_stats.input ({len(ds_inputs)} domains) ===")
        for d in ds_inputs:
            print(f"  {d.get('Domain')} | Type: {d.get('DomainType')} | Company: {d.get('Company')} | empId: {d.get('employerId')}")
    except Exception as e:
        print("Mongo query error:", e)
