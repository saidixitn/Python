import os
import re
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

print("Fetching all posted QRM jobs...")
cursor = job_col.find(
    {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"},
    {"jobId": 1, "submittedUrl": 1, "description": 1, "location": 1, "title": 1}
)
jobs = list(cursor)
print(f"Total posted jobs: {len(jobs)}")

matched_issue_jobs = []

for j in jobs:
    jid = j["jobId"]
    sub_url = j.get("submittedUrl", "")
    desc = j.get("description", "")
    loc = j.get("location", "")
    title = j.get("title", "")
    
    issues = []
    
    # 1. Missing space before "has an exciting opportunity" or "is seeking" (e.g. Centerhas, Parkhas)
    m_has = re.findall(r'([a-zA-Z0-9](?:has an exciting opportunity|is seeking))', desc)
    if m_has:
        issues.append(f"Missing space before verb: {', '.join(set(m_has[:3]))}")
        
    # 2. Glued "for aFull-Time" or "for aFull-time"
    if re.search(r'for aFull-time|for aFull-Time|\baFull-Time\b|\baFull-time\b', desc, re.IGNORECASE):
        issues.append("Missing space: aFull-Time")
        
    # 3. Glued acronym to next sentence e.g. (OTA)We, (OT)We, (PT)We
    m_acronym = re.findall(r'\([A-Z]{2,4}\)[A-Z]', desc)
    if m_acronym:
        issues.append(f"Missing period/space after acronym: {', '.join(set(m_acronym[:3]))}")
        
    # 4. Glued "At<Word>" e.g. AtSt., AtNexus, AtRoyal, etc.
    m_at = re.findall(r'\bAt[A-Z][a-z]+', desc)
    if m_at:
        issues.append(f"Missing space in At: {', '.join(set(m_at[:3]))}")
        
    # 5. Missing state in license requirement: "license ."
    if "license ." in desc:
        issues.append("Missing state in license: 'license .'")
        
    # 6. Unclosed <strong> tag
    if desc.count("<strong") > desc.count("</strong"):
        issues.append("Unclosed <strong> tag")
        
    # 7. Broken paragraph structure (<p>...<p> without </p>)
    if desc.count("<p") > desc.count("</p"):
        issues.append("Unclosed <p> tag")

    if issues:
        matched_issue_jobs.append({
            "jobId": jid,
            "SubmittedUrl": sub_url,
            "Job Title": title,
            "Location": loc,
            "Issues Detected": " | ".join(issues),
            "org_desc": desc
        })

print(f"\nJobs matching the issue pattern from user sample: {len(matched_issue_jobs)}")

# Let's inspect frequency of specific issues
issue_counts = {}
for item in matched_issue_jobs:
    for iss in item["Issues Detected"].split(" | "):
        base_iss = iss.split(":")[0]
        issue_counts[base_iss] = issue_counts.get(base_iss, 0) + 1

print("\nBreakdown of issues detected:")
for k, v in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {k}: {v}")

# Save to CSV
out_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_description_issues_jobs.csv"
pd.DataFrame(matched_issue_jobs).to_csv(out_csv, index=False)
print(f"\nSaved issues CSV to: {out_csv}")

# Also copy to artifacts directory
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935"
artifact_csv = os.path.join(artifact_dir, "qrm_description_issues_jobs.csv")
pd.DataFrame(matched_issue_jobs).to_csv(artifact_csv, index=False)
print(f"Saved artifact copy to: {artifact_csv}")

# Also create a lighter version without org_desc for quick viewing
summary_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_description_issues_summary.csv"
pd.DataFrame(matched_issue_jobs)[["jobId", "SubmittedUrl", "Job Title", "Location", "Issues Detected"]].to_csv(summary_csv, index=False)
pd.DataFrame(matched_issue_jobs)[["jobId", "SubmittedUrl", "Job Title", "Location", "Issues Detected"]].to_csv(os.path.join(artifact_dir, "qrm_description_issues_summary.csv"), index=False)
print(f"Saved summary CSV to: {summary_csv}")
