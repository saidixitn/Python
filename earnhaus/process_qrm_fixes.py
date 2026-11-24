import os
import re
import time
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup

t_start = time.time()

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

print("[1/3] Fetching all posted QRM jobs from prod_jobiak_ai.job...")
cursor = job_col.find(
    {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"},
    {"jobId": 1, "submittedUrl": 1, "description": 1, "location": 1, "title": 1}
)
jobs = list(cursor)
print(f"Retrieved {len(jobs)} posted jobs in {time.time() - t_start:.2f}s.")

def fix_description(desc, location_str=""):
    if not desc:
        return desc
    
    modified = desc
    
    # 1. Spacing before common phrases
    modified = re.sub(r'([a-zA-Z0-9])has an exciting opportunity', r'\1 has an exciting opportunity', modified)
    modified = re.sub(r'([a-zA-Z0-9])is seeking', r'\1 is seeking', modified)
    modified = re.sub(r'for aFull-Time', r'for a Full-Time', modified, flags=re.IGNORECASE)
    modified = re.sub(r'for aFull-time', r'for a Full-time', modified, flags=re.IGNORECASE)
    modified = re.sub(r'for aPRN', r'for a PRN', modified, flags=re.IGNORECASE)
    modified = re.sub(r'for aPart-Time', r'for a Part-Time', modified, flags=re.IGNORECASE)
    modified = re.sub(r'\baFull-Time\b', r'a Full-Time', modified)
    modified = re.sub(r'\baFull-time\b', r'a Full-time', modified)
    modified = re.sub(r'compassionatePRN', r'compassionate PRN', modified)
    
    # 2. Acronyms followed immediately by capital letter or 'in' e.g. (OTA)We -> (OTA). We
    modified = re.sub(r'\(([A-Z]{2,4})\)([A-Z])', r'(\1). \2', modified)
    modified = re.sub(r'\(([A-Z]{2,4})\)in([A-Z])', r'(\1) in \2', modified)
    
    # 3. "in<City>" e.g. inWayland -> in Wayland, inNiles -> in Niles, inElmwood -> in Elmwood
    modified = re.sub(r'(?<=\s)in([A-Z][a-z]+)', r'in \1', modified)
    modified = re.sub(r'(?<=\))in([A-Z][a-z]+)', r' in \1', modified)
    modified = re.sub(r'(?<=\>)in([A-Z][a-z]+)', r'in \1', modified)
    
    # 4. "At<Word>" e.g. AtSt. -> At St., AtNexus -> At Nexus, AtRoyal -> At Royal, AtAward -> At Award
    modified = re.sub(r'\bAt([A-Z][a-z]+)', r'At \1', modified)
    modified = re.sub(r'\bAtSt\.', r'At St.', modified)
    
    # 5. Missing state in license requirement: "license ."
    state = ""
    if location_str and "," in location_str:
        parts = [p.strip() for p in location_str.split(",")]
        if len(parts) >= 2 and len(parts[1]) == 2:
            state = parts[1]
    if "license ." in modified:
        if state:
            modified = modified.replace("license .", f"license in {state}.")
        else:
            modified = modified.replace("license .", "license.")
            
    # 6. Missing space after period between sentences e.g. "team.At" -> "team. At"
    modified = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', modified)
    
    # 7. Unclosed <strong> tag fixing:
    if modified.count("<strong") > modified.count("</strong"):
        m_headline = re.search(r'<strong>([A-Za-z0-9\s&\'.,-]+?(?:has an exciting opportunity for a[A-Za-z0-9\s&\'.,-]+?\([A-Z]{2,4}\)|is seeking a compassionate[A-Za-z0-9\s&\'.,-]+?\([A-Z]{2,4}\)))(?!\s*</strong>)', modified)
        if m_headline:
            full_match = m_headline.group(0)
            inner = m_headline.group(1)
            modified = modified.replace(full_match, f"<strong>{inner}</strong>")
            
    # 8. Use BeautifulSoup to clean and balance all remaining unclosed tags (<p>, <strong>, <ul>, etc.)
    soup = BeautifulSoup(modified, "html.parser")
    clean_html = "".join(str(item) for item in soup.contents)
    
    return clean_html

print("[2/3] Analyzing and fixing descriptions...")
t1 = time.time()
records = []
changed_count = 0

for j in jobs:
    jid = j["jobId"]
    sub_url = j.get("submittedUrl") or ""
    org_desc = j.get("description") or ""
    loc = j.get("location") or ""
    
    mod_desc = fix_description(org_desc, loc)
    
    is_changed = (org_desc != mod_desc)
    if is_changed:
        changed_count += 1
        records.append({
            "jobId": jid,
            "SubmittedUrl": sub_url,
            "org_desc": org_desc,
            "mod_desc": mod_desc
        })

print(f"Processed {len(jobs)} jobs in {time.time() - t1:.2f}s.")
print(f"Jobs with description issues found & modified: {changed_count}")

# 3. Save to CSV
print("[3/3] Saving results to CSV...")
out_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_description_fixes.csv"
pd.DataFrame(records).to_csv(out_csv, index=False)
print(f"Saved {len(records)} modified jobs to {out_csv}")

artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935"
artifact_csv = os.path.join(artifact_dir, "qrm_posted_jobs_description_fixes.csv")
pd.DataFrame(records).to_csv(artifact_csv, index=False)
print(f"Saved artifact copy to {artifact_csv}")

print(f"\nTotal script execution time: {time.time() - t_start:.2f}s.")

print("\nSample modified jobs (first 3):")
for r in records[:3]:
    print("=" * 60)
    print("JobId:", r["jobId"])
    print("SubmittedUrl:", r["SubmittedUrl"])
    print("org_desc preview:", r["org_desc"][:200])
    print("mod_desc preview:", r["mod_desc"][:200])
