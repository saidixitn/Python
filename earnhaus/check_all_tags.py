import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

query = {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"}
jobs = list(job_col.find(query, {"jobId": 1, "description": 1}))

other_tag_counts = {}
for j in jobs:
    desc = j.get("description", "") or ""
    # Check each tag
    for tag in ['strong', 'b', 'em', 'i', 'u', 'p', 'ul', 'ol', 'li']:
        open_c = len(re.findall(rf'<{tag}\b[^>]*>', desc, re.I))
        close_c = len(re.findall(rf'</{tag}\s*>', desc, re.I))
        if open_c != close_c:
            other_tag_counts[tag] = other_tag_counts.get(tag, 0) + 1

print("Tag imbalance across all 2829 jobs:")
for tag, count in other_tag_counts.items():
    print(f"Tag <{tag}>: {count} jobs have mismatched open vs close")
