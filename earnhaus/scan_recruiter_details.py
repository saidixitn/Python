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

print("=== Scanning 20 docs from emp-qrm ===")
for doc in emp_qrm.find({}, {"description": 1, "title": 1}).limit(20):
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # Check lines after 'confidential' or looking like recruiter names/emails/phones
    confidential_found = False
    for i, line in enumerate(lines):
        if "confidential" in line.lower():
            print(f"Doc: {doc.get('title')}")
            print(f"  Confidential line: {line}")
            for nxt in lines[i+1:i+6]:
                print(f"    After: {nxt}")
            confidential_found = True
            break

print("\n=== Scanning 20 docs from Target_P4_Opt ===")
for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1, "jobtitle": 1}).limit(20):
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    for i, line in enumerate(lines):
        if any(k in line.lower() for k in ["confidential", "contact", "recruiter", "rebecca", "henderson", "@", "phone", "email"]):
            print(f"Doc: {doc.get('jobtitle')}")
            print(f"  Match line: {line}")
            for nxt in lines[i+1:i+4]:
                print(f"    After: {nxt}")
            break
