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

recruiter_names = set()
recruiter_blocks = set()

def find_recruiters(desc):
    if not desc:
        return
    # Match patterns like:
    # Recruiter Contact Information: ... Name ... Phone ... Email
    # or Rebecca Henderson
    # Let's search for "Recruiter Contact Information"
    m = re.search(r'(?:Recruiter\s*Contact\s*Information|Recruiter\s*Contact|Recruiter\s*information)[^<>\n]*[:\s]*(?:<[^>]+>|\s)*([^<>\n\r]+?)(?:<[^>]+>|\s)*(\d{3}[-.\s]\d{3}[-.\s]\d{4}|\w+@\w+)', desc, re.I)
    if m:
        name_candidate = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        # Clean up
        name_candidate = re.sub(r'^(?:name[:\s]*|contact[:\s]*|for inquiries[:\s]*)', '', name_candidate, flags=re.I).strip()
        if name_candidate and len(name_candidate.split()) in [2, 3] and not any(x in name_candidate.lower() for x in ['qrm', 'health', 'apply', 'opportunity', 'http', 'line']):
            recruiter_names.add(name_candidate)

    # Also match before @qrmhealth.com
    for m2 in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})[\s<>&;a-z0-9=:"\'-]{0,60}?[a-zA-Z0-9_.+-]+@qrmhealth\.com', desc, re.I):
        c = re.sub(r'<[^>]+>', '', m2.group(1)).strip()
        if c and len(c.split()) in [2, 3] and not any(x in c.lower() for x in ['rehab', 'management', 'inquiries', 'confidential', 'opportunities', 'health']):
            recruiter_names.add(c)

print("Scanning emp-qrm for recruiter names...")
for doc in emp_qrm.find({}, {"description": 1}).batch_size(2000):
    find_recruiters(doc.get("description", ""))

print("Scanning Target_P4_Opt for recruiter names...")
for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1}).batch_size(2000):
    find_recruiters(doc.get("description", ""))

print(f"Found {len(recruiter_names)} Recruiter Names:")
for name in sorted(list(recruiter_names)):
    print(" ", repr(name))
