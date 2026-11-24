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

df = pd.read_csv(r"C:/Users/JOBIAK/.gemini/antigravity/brain/6e0488a6-8f1e-4ae7-9214-e018b0901935/.user_uploaded/media_1793970059780_660dbf16.csv")
all_records = df.to_dict("records")
all_ids = [r["jobId"] for r in all_records]

# Fetch all
docs = []
for i in range(0, len(all_ids), 1000):
    batch = all_ids[i:i+1000]
    cursor = job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1, "title": 1})
    docs.extend(list(cursor))

doc_map = {d["jobId"]: d for d in docs}

# Let's inspect where "Wayland" appears
wayland_jobs = []
for d in docs:
    desc = d.get("description", "")
    if "wayland" in desc.lower():
        wayland_jobs.append(d["jobId"])

print(f"Total jobs with 'Wayland' in description: {len(wayland_jobs)}")

# Let's find snippets around "Wayland" in these descriptions to see exactly how "Wayland, MA" is written
for jid in wayland_jobs[:5]:
    desc = doc_map[jid].get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    idx = text.lower().find("wayland")
    print("--- SNIPPET FOR", jid, "---")
    print(text[max(0, idx-50):min(len(text), idx+100)])
