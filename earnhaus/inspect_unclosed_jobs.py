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
projection = {"jobId": 1, "submittedUrl": 1, "description": 1, "title": 1, "location": 1}

all_jobs = []
last_id = None
while True:
    q = dict(query)
    if last_id:
        q["_id"] = {"$gt": last_id}
    batch = list(job_col.find(q, projection).sort("_id", 1).limit(500))
    if not batch:
        break
    all_jobs.extend(batch)
    last_id = batch[-1]["_id"]

print(f"Total jobs: {len(all_jobs)}")

# Let's inspect tag mismatches:
unclosed_strong_jobs = []
unclosed_p_jobs = []
other_issues_jobs = []

for j in all_jobs:
    jid = j.get("jobId", "")
    url = j.get("submittedUrl", "")
    desc = j.get("description", "") or ""
    
    s_open = len(re.findall(r'<strong\b[^>]*>', desc, re.I))
    s_close = len(re.findall(r'</strong\s*>', desc, re.I))
    
    p_open = len(re.findall(r'<p\b[^>]*>', desc, re.I))
    p_close = len(re.findall(r'</p\s*>', desc, re.I))
    
    has_doubled_strong = bool(re.search(r'<strong>\s*<strong>', desc, re.I))
    
    # check unclosed strong inside li
    unclosed_li_strong = bool(re.search(r'<li>\s*<strong>(?!.*?</strong>).*?</li>', desc, re.I | re.DOTALL))
    
    # check unclosed strong before <p>
    unclosed_strong_before_p = bool(re.search(r'<strong>(?!.*?</strong>).*?<p>', desc, re.I | re.DOTALL))
    
    if s_open != s_close or has_doubled_strong or unclosed_li_strong:
        unclosed_strong_jobs.append({
            "jobId": jid,
            "url": url,
            "s_open": s_open,
            "s_close": s_close,
            "has_doubled_strong": has_doubled_strong,
            "unclosed_li_strong": unclosed_li_strong,
            "unclosed_strong_before_p": unclosed_strong_before_p,
            "p_open": p_open,
            "p_close": p_close
        })
    elif p_open != p_close:
        unclosed_p_jobs.append({
            "jobId": jid,
            "url": url,
            "p_open": p_open,
            "p_close": p_close
        })

print(f"Jobs with unclosed/malformed <strong>: {len(unclosed_strong_jobs)}")
print(f"Jobs with unclosed <p> (and balanced strong): {len(unclosed_p_jobs)}")

# Look at 5 samples of unclosed_p_jobs to see what happened to them:
print("\nSample unclosed <p> jobs:")
for item in unclosed_p_jobs[:5]:
    j_doc = next(x for x in all_jobs if x['jobId'] == item['jobId'])
    d = j_doc.get("description", "")
    print(f"\n--- JobId: {item['jobId']} (p_open: {item['p_open']}, p_close: {item['p_close']}) ---")
    # print first 500 chars
    print(d[:500])
