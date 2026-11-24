import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

fine_ids = [
    "6ae9cc41673a5103d5021031",
    "6ae4a6c0b472b803804d7b5c",
    "6ae0a5995b89f003f208eafa",
    "6ae1d9eb855f8c0394f3822f"
]

issue_ids = [
    "6adf3d332056e50380a450cc",
    "6adc9709e376156cb260f4fe",
    "6adc96256de9da0407e345d4",
    "6adf3cdd44ab7804720b513c"
]

print("=== FINE JOBS ===")
for jid in fine_ids:
    doc = job_col.find_one({"jobId": jid}, {"description": 1, "title": 1})
    desc = doc.get("description", "") if doc else "NOT FOUND"
    print(f"JID: {jid}")
    print(f"  <strong: {desc.count('<strong')}, </strong: {desc.count('</strong')}")
    print(f"  <p: {desc.count('<p')}, </p: {desc.count('</p')}")
    print(f"  First 300 chars: {desc[:300]}")
    print()

print("=== ISSUE JOBS ===")
for jid in issue_ids:
    doc = job_col.find_one({"jobId": jid}, {"description": 1, "title": 1})
    desc = doc.get("description", "") if doc else "NOT FOUND"
    print(f"JID: {jid}")
    print(f"  <strong: {desc.count('<strong')}, </strong: {desc.count('</strong')}")
    print(f"  <p: {desc.count('<p')}, </p: {desc.count('</p')}")
    print(f"  First 300 chars: {desc[:300]}")
    print()
