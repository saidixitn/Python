from pymongo import MongoClient
import os
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

emp_qrm = db["emp-qrm"]
target_p4 = db["Target_P4_Opt"]

# Scan Target_P4_Opt for any recruiter or email or phone
print("Checking Target_P4_Opt for emails, phones, or recruiter...")
target_matches = []
for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1, "jobtitle": 1, "city": 1, "state": 1}).limit(500):
    desc = doc.get("description", "")
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', desc)
    phones = re.findall(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', desc)
    recruiter = re.findall(r'recruiter[^<>\n]*', desc, re.I)
    if emails or phones or recruiter:
        target_matches.append({
            "emails": emails,
            "phones": phones,
            "recruiter": recruiter,
            "desc_snippet": desc[:200]
        })

print(f"Target_P4_Opt samples with recruiter info: {len(target_matches)}")
if target_matches:
    print(target_matches[:5])
else:
    print("No emails/phones in first 500 Target_P4_Opt docs. Checking if locations exist...")
    # Check if City, State exists in Target_P4_Opt descriptions
    for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1}).limit(20):
        desc = doc.get("description", "")
        # find City, ST pattern
        m = re.findall(r'\b[A-Z][a-zA-Z\s.-]+?,\s*[A-Z]{2}\b', desc)
        if m:
            print("  Target doc City, State matches:", [x for x in m if "LLC" not in x][:5])
