import os
import re
import csv
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

query = {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"}
projection = {"jobId": 1, "submittedUrl": 1, "description": 1, "title": 1}

print("Fetching all posted QRM jobs...")
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

print(f"Total posted QRM jobs fetched: {len(all_jobs)}")

def fix_missing_tags(html_str):
    if not html_str:
        return ""
    
    # 1. Clean up duplicated <strong><strong> tags
    fixed = re.sub(r'<strong>\s*<strong>', '<strong>', html_str, flags=re.I)
    fixed = re.sub(r'</strong>\s*</strong>', '</strong>', fixed, flags=re.I)
    
    # 2. Fix <li><strong>text</li> where </strong> is missing
    def fix_li(m):
        prefix = m.group(1)
        content = m.group(2)
        suffix = m.group(3)
        if '</strong>' not in content:
            return f"{prefix}{content}</strong>{suffix}"
        return m.group(0)

    fixed = re.sub(r'(<li>\s*<strong>)(.*?)(</li>)', fix_li, fixed, flags=re.I | re.DOTALL)
    
    # 3. Fix unclosed <strong> before opening <p> (like in OTA example)
    # e.g., </p><strong>Some intro text...<p> -> </p><p><strong>Some intro text...</strong></p><p> or close </strong> before <p>
    def fix_unclosed_strong_before_p(m):
        content = m.group(1)
        if '</strong>' not in content:
            return f"<p><strong>{content}</strong></p><p>"
        return m.group(0)

    fixed = re.sub(r'<strong>(?!.*?</strong>)(.*?)<p>', fix_unclosed_strong_before_p, fixed, flags=re.I | re.DOTALL)

    # 4. Fix <p><strong>Heading</strong><ul> (missing </p> before <ul>)
    fixed = re.sub(r'(<p>\s*<strong>.*?</strong>\s*)(<ul>)', r'\1</p>\2', fixed, flags=re.I | re.DOTALL)

    # 5. Fix <p><strong>Heading</strong><p> (missing </p> between headings)
    fixed = re.sub(r'(<p>\s*<strong>.*?</strong>\s*)(<p>)', r'\1</p>\2', fixed, flags=re.I | re.DOTALL)

    # 6. Clean dangling </p></p>
    fixed = re.sub(r'(</p>\s*){2,}', '</p>', fixed, flags=re.I)

    # 7. Use BeautifulSoup to balance all remaining unbalanced tags cleanly
    soup = BeautifulSoup(fixed, 'html.parser')
    clean_html = str(soup)
    
    return clean_html

issue_records = []

for j in all_jobs:
    jid = j.get("jobId", "")
    url = j.get("submittedUrl", "")
    org_desc = j.get("description", "") or ""
    
    s_open = len(re.findall(r'<strong\b[^>]*>', org_desc, re.I))
    s_close = len(re.findall(r'</strong\s*>', org_desc, re.I))
    
    p_open = len(re.findall(r'<p\b[^>]*>', org_desc, re.I))
    p_close = len(re.findall(r'</p\s*>', org_desc, re.I))
    
    has_doubled_strong = bool(re.search(r'<strong>\s*<strong>', org_desc, re.I))
    unclosed_li_strong = bool(re.search(r'<li>\s*<strong>(?!.*?</strong>).*?</li>', org_desc, re.I | re.DOTALL))
    unclosed_strong_before_p = bool(re.search(r'<strong>(?!.*?</strong>).*?<p>', org_desc, re.I | re.DOTALL))
    missing_p_close_before_ul = bool(re.search(r'<p>\s*<strong>.*?</strong>\s*<ul>', org_desc, re.I | re.DOTALL))
    dangling_p_close = bool(re.search(r'</p>\s*</p>', org_desc, re.I))
    
    has_tag_issue = (
        (s_open != s_close) or 
        has_doubled_strong or 
        unclosed_li_strong or 
        unclosed_strong_before_p or 
        (p_open != p_close) or 
        missing_p_close_before_ul or 
        dangling_p_close
    )
    
    if has_tag_issue:
        mod_desc = fix_missing_tags(org_desc)
        issue_records.append({
            "jobId": jid,
            "SubmittedUrl": url,
            "org_desc": org_desc,
            "mod_desc": mod_desc
        })

print(f"Total jobs with missing/malformed HTML tags: {len(issue_records)}")

# Write to CSV
artifact_csv = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_missing_tags_jobs.csv"
local_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv"

for csv_path in [artifact_csv, local_csv]:
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jobId", "SubmittedUrl", "org_desc", "mod_desc"])
        writer.writeheader()
        writer.writerows(issue_records)

print(f"Successfully saved {len(issue_records)} records to CSV files!")
