from pymongo import MongoClient
import os
import re
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

emp_qrm = db["emp-qrm"]
target_p4 = db["Target_P4_Opt"]

with open(r"c:\Users\JOBIAK\Documents\Python\earnhaus\extracted_recruiter.txt", "r") as f:
    text = f.read()

emails = [l.strip() for l in text.split("=== PHONES ===")[0].split("=== EMAILS ===")[1].split("\n") if l.strip()]
print(f"Total distinct emails: {len(emails)}")

recruiter_blocks = set()

# For each email, find 1 sample in emp-qrm or target_p4 and see the full block
for em in emails[:15]:
    # Query emp-qrm
    doc = emp_qrm.find_one({"description": {"$regex": re.escape(em)}}, {"description": 1})
    if not doc:
        doc = target_p4.find_one({"employerId": "emp-jicn-qrm", "description": {"$regex": re.escape(em)}}, {"description": 1})
    if doc:
        desc = doc.get("description", "")
        # find the paragraph or div containing this email
        idx = desc.find(em)
        start = max(0, idx - 200)
        end = min(len(desc), idx + 200)
        snippet = desc[start:end]
        # Clean tags to see text
        plain_snippet = re.sub(r'<[^>]+>', '\n', snippet)
        plain_snippet = "\n".join([l.strip() for l in plain_snippet.split("\n") if l.strip()])
        print(f"\n--- Email: {em} ---")
        print("Raw Snippet:", repr(snippet))
        print("Clean Snippet:\n", plain_snippet)
