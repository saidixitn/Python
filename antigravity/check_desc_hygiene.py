import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from collections import Counter
import pandas as pd

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
pj_uri = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
pj_client = MongoClient(pj_uri)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"
jobs = list(db.job.find({"employerId": emp_id, "status": "posted"}, {
    "jobId": 1, "title": 1, "location": 1, "description": 1, "clientJobId": 1, "url": 1
}))

print(f"Total posted jobs: {len(jobs)}")

# Let's inspect length, encoding artifacts, broken tags
broken_strong = []
broken_p = []
encoding_artifacts = []
short_descs = []

for j in jobs:
    jid = j["jobId"]
    desc = j.get("description", "")
    
    # Check length
    if len(desc) < 500:
        short_descs.append((jid, j.get("title"), len(desc)))
        
    # Check strong tags match
    if desc.count("<strong") != desc.count("</strong"):
        broken_strong.append((jid, desc.count("<strong"), desc.count("</strong")))
        
    # Check p tags match
    if desc.count("<p") != desc.count("</p"):
        broken_p.append((jid, desc.count("<p"), desc.count("</p")))
        
    # Check mojibake / bad encoding
    if any(bad in desc for bad in ["â€™", "â€œ", "â€", "Â", "Ã"]):
        encoding_artifacts.append(jid)

print(f"Jobs with unclosed <strong tags: {len(broken_strong)}")
print(f"Jobs with unclosed <p tags: {len(broken_p)}")
print(f"Jobs with Mojibake / encoding artifacts (â€™, etc.): {len(encoding_artifacts)}")
print(f"Jobs with very short description (< 500 chars): {len(short_descs)}")
