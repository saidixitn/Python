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
jobs = list(job_col.find(query, {"jobId": 1, "submittedUrl": 1, "description": 1, "title": 1}))

print(f"Total jobs: {len(jobs)}")

issue_jobs = []

for j in jobs:
    jid = j.get("jobId", "")
    url = j.get("submittedUrl", "")
    desc = j.get("description", "") or ""
    
    # 1. strong mismatch
    s_open = len(re.findall(r'<strong\b[^>]*>', desc, re.I))
    s_close = len(re.findall(r'</strong\s*>', desc, re.I))
    
    # 2. doubled strong
    has_doubled_strong = bool(re.search(r'<strong>\s*<strong>', desc, re.I))
    
    # 3. strong opened inside li without closing before </li>
    unclosed_li_strong = bool(re.search(r'<li>\s*<strong>(?!.*?</strong>).*?</li>', desc, re.I | re.DOTALL))
    
    # 4. p tag mismatch
    p_open = len(re.findall(r'<p\b[^>]*>', desc, re.I))
    p_close = len(re.findall(r'</p\s*>', desc, re.I))
    
    is_issue = (s_open != s_close) or has_doubled_strong or unclosed_li_strong or (p_open != p_close)
    
    if is_issue:
        issue_jobs.append({
            "jobId": jid,
            "url": url,
            "s_open": s_open,
            "s_close": s_close,
            "has_doubled_strong": has_doubled_strong,
            "unclosed_li_strong": unclosed_li_strong,
            "p_open": p_open,
            "p_close": p_close
        })

print(f"Total issue jobs found: {len(issue_jobs)}")

# Breakdown:
only_strong = [x for x in issue_jobs if (x['s_open'] != x['s_close'] or x['has_doubled_strong'] or x['unclosed_li_strong']) and x['p_open'] == x['p_close']]
only_p = [x for x in issue_jobs if (x['s_open'] == x['s_close'] and not x['has_doubled_strong'] and not x['unclosed_li_strong']) and x['p_open'] != x['p_close']]
both = [x for x in issue_jobs if (x['s_open'] != x['s_close'] or x['has_doubled_strong'] or x['unclosed_li_strong']) and x['p_open'] != x['p_close']]

print(f"Breakdown:")
print(f"  Only Strong issues (unclosed/doubled): {len(only_strong)}")
print(f"  Only P tag issues: {len(only_p)}")
print(f"  Both Strong and P tag issues: {len(both)}")
print(f"  Total with strong issues: {len(only_strong) + len(both)}")
