import os
import re
import csv
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

print("Fetching all posted QRM jobs from DB...")
cursor = job_col.find(
    {"employerId": "6a7b516d060e8f0b78b0dc5a", "status": "posted"},
    {"jobId": 1, "description": 1, "location": 1, "title": 1, "datePosted": 1, "submittedUrl": 1}
)
posted_jobs = list(cursor)
print(f"Total posted jobs: {len(posted_jobs)}")

US_STATE_CODES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'
city_state_pat = re.compile(rf'\b([A-Z][a-zA-Z\s.-]+?),\s*({US_STATE_CODES})\b')
in_pat = re.compile(rf'\bin\s*([A-Za-z\s]+?),\s*({US_STATE_CODES})\b', re.IGNORECASE)
false_positives = {"Rehab Management", "Management", "LLC", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"}

records_all_no_loc = []

for j in posted_jobs:
    jid = j.get("jobId")
    desc = j.get("description", "") or ""
    date_posted = j.get("datePosted")
    # format date_posted cleanly if datetime
    if hasattr(date_posted, "strftime"):
        date_str = date_posted.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_str = str(date_posted) if date_posted else ""

    text = re.sub(r'<[^>]+>', ' ', desc)
    
    detected = []
    for m in city_state_pat.finditer(text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in false_positives and len(c) > 2 and not any(c.endswith(fp) for fp in ["Therapist", "Assistant"]):
            detected.append(f"{c}, {s}")
            
    for m in in_pat.finditer(text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in false_positives and len(c) > 2:
            detected.append(f"{c}, {s}")
            
    has_loc = (len(detected) > 0)
    
    if not has_loc:
        records_all_no_loc.append({
            "jobId": jid,
            "datePosted": date_str,
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "submittedUrl": j.get("submittedUrl", "")
        })

print(f"Total posted jobs with NO location in description: {len(records_all_no_loc)}")

# Sort by datePosted descending
records_all_no_loc.sort(key=lambda x: x["datePosted"], reverse=True)

# Write full CSV with jobId, datePosted, title, location, submittedUrl
artifact_path = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_posted_jobs_no_location_dateposted.csv"
local_path = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_no_location_dateposted.csv"

for p in [artifact_path, local_path]:
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jobId", "datePosted", "title", "location", "submittedUrl"])
        writer.writeheader()
        writer.writerows(records_all_no_loc)

# Also write minimalist 2-column CSV with just jobId and datePosted
artifact_2col = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_posted_jobids_dateposted.csv"
local_2col = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobids_dateposted.csv"

for p in [artifact_2col, local_2col]:
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jobId", "datePosted"])
        writer.writeheader()
        for r in records_all_no_loc:
            writer.writerow({"jobId": r["jobId"], "datePosted": r["datePosted"]})

print("Successfully written all output CSV files!")
