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
print(f"Total posted jobs found: {len(jobs)}")

# Let's inspect common spacing and tag issues across all jobs
spacing_issues = []
tag_issues = []

for j in jobs:
    desc = j.get("description", "")
    jid = j["jobId"]
    
    # Check for missing spaces
    has_issue = False
    
    # 1. Words ending in letters + "has an exciting" or "is seeking" without space
    m1 = re.findall(r'[a-zA-Z](?:has an exciting|is seeking|for aFull|for aPRN)', desc)
    # 2. "license ."
    m2 = "license ." in desc
    # 3. "(OT)We", "(PT)We", "(OTA)We", "(SLP)We", "(PTA)We"
    m3 = re.findall(r'\([A-Z]{2,4}\)[A-Z]', desc)
    # 4. "in[A-Z]" e.g. "inWayland", "inNiles", "inEast"
    m4 = re.findall(r'\bin[A-Z][a-z]+', desc)
    # 5. "AtSt." or "At[A-Z]" without space
    m5 = re.findall(r'\bAt[A-Z][a-z]+', desc)
    # 6. Unclosed strong or p tag issues
    unclosed_strong = desc.count("<strong") > desc.count("</strong")
    unclosed_p = desc.count("<p") > desc.count("</p")
    
    if m1 or m2 or m3 or m4 or m5:
        spacing_issues.append((jid, m1 + (["license ."] if m2 else []) + m3 + m4 + m5))
    if unclosed_strong or unclosed_p:
        tag_issues.append((jid, unclosed_strong, unclosed_p))

print(f"Jobs with spacing issues: {len(spacing_issues)}")
print(f"Jobs with unclosed tags: {len(tag_issues)}")
if spacing_issues:
    print("Sample spacing issues detected:")
    for jid, issues in spacing_issues[:10]:
        print(f"  {jid}: {issues}")
