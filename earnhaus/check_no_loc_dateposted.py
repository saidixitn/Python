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
    {"jobId": 1, "description": 1, "location": 1, "title": 1, "datePosted": 1}
)
posted_jobs = list(cursor)
print(f"Total posted QRM jobs in DB: {len(posted_jobs)}")

US_STATE_CODES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'
city_state_pat = re.compile(rf'\b([A-Z][a-zA-Z\s.-]+?),\s*({US_STATE_CODES})\b')
in_pat = re.compile(rf'\bin\s*([A-Za-z\s]+?),\s*({US_STATE_CODES})\b', re.IGNORECASE)
false_positives = {"Rehab Management", "Management", "LLC", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"}

no_loc_all_posted = []

for j in posted_jobs:
    jid = j.get("jobId")
    desc = j.get("description", "") or ""
    date_posted = j.get("datePosted")
    
    # Strip html
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
        no_loc_all_posted.append({
            "jobId": jid,
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "datePosted": date_posted
        })

print(f"Total posted jobs with NO location in description: {len(no_loc_all_posted)}")
print(f"Total posted jobs WITH location in description: {len(posted_jobs) - len(no_loc_all_posted)}")

# Check against 327 issue jobs
df_327 = pd.read_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_final.csv")
issue_327_ids = set(df_327["jobId"].tolist())

issue_and_no_loc = [x for x in no_loc_all_posted if x["jobId"] in issue_327_ids]
print(f"Jobs that have description tag issues AND no location in description: {len(issue_and_no_loc)}")

# Also check against the user uploaded 2666 jobs CSV
uploaded_df = pd.read_csv(r"C:/Users/JOBIAK/.gemini/antigravity/brain/6e0488a6-8f1e-4ae7-9214-e018b0901935/.user_uploaded/media_1793970059780_660dbf16.csv")
uploaded_ids = set(uploaded_df["jobId"].tolist())
uploaded_no_loc = [x for x in no_loc_all_posted if x["jobId"] in uploaded_ids]
print(f"Jobs from uploaded CSV that are posted and have no location in description: {len(uploaded_no_loc)}")
