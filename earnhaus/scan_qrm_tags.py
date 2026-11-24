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
projection = {"jobId": 1, "submittedUrl": 1, "description": 1, "title": 1}

print("Fetching posted QRM jobs...")
cursor = job_col.find(query, projection)
jobs = list(cursor)
print(f"Total posted QRM jobs fetched: {len(jobs)}")

mismatched_strong = []
mismatched_other = []

for j in jobs:
    jid = j.get("jobId", "")
    desc = j.get("description", "") or ""
    
    strong_open = len(re.findall(r'<strong\b[^>]*>', desc, re.I))
    strong_close = len(re.findall(r'</strong\s*>', desc, re.I))
    
    b_open = len(re.findall(r'<b\b[^>]*>', desc, re.I))
    b_close = len(re.findall(r'</b\s*>', desc, re.I))
    
    em_open = len(re.findall(r'<em\b[^>]*>', desc, re.I))
    em_close = len(re.findall(r'</em\s*>', desc, re.I))
    
    i_open = len(re.findall(r'<i\b[^>]*>', desc, re.I))
    i_close = len(re.findall(r'</i\s*>', desc, re.I))
    
    ul_open = len(re.findall(r'<ul\b[^>]*>', desc, re.I))
    ul_close = len(re.findall(r'</ul\s*>', desc, re.I))

    p_open = len(re.findall(r'<p\b[^>]*>', desc, re.I))
    p_close = len(re.findall(r'</p\s*>', desc, re.I))

    li_open = len(re.findall(r'<li\b[^>]*>', desc, re.I))
    li_close = len(re.findall(r'</li\s*>', desc, re.I))
    
    has_doubled = bool(re.search(r'<(strong|b)[^>]*>\s*<(strong|b)[^>]*>', desc, re.I))
    
    has_strong_issue = (strong_open != strong_close) or has_doubled
    has_other_issue = (b_open != b_close) or (em_open != em_close) or (i_open != i_close) or (ul_open != ul_close) or (p_open != p_close) or (li_open != li_close)
    
    if has_strong_issue:
        mismatched_strong.append({
            "jobId": jid,
            "strong_open": strong_open,
            "strong_close": strong_close,
            "has_doubled": has_doubled,
            "submittedUrl": j.get("submittedUrl", "")
        })
    elif has_other_issue:
        mismatched_other.append({
            "jobId": jid,
            "b": (b_open, b_close),
            "em": (em_open, em_close),
            "i": (i_open, i_close),
            "ul": (ul_open, ul_close),
            "p": (p_open, p_close),
            "li": (li_open, li_close)
        })

print(f"Jobs with strong mismatch or doubled strong: {len(mismatched_strong)}")
print(f"Jobs with other tag mismatches: {len(mismatched_other)}")

if mismatched_strong:
    print("\nSample mismatched strong jobs:")
    for item in mismatched_strong[:5]:
        print(item)
