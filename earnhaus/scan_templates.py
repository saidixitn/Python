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
all_ids = df["jobId"].tolist()
print(f"Total jobIds in CSV: {len(all_ids)}")

# Let's fetch in batches of 1000
docs = []
for i in range(0, len(all_ids), 1000):
    batch = all_ids[i:i+1000]
    cursor = job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1, "title": 1})
    docs.extend(list(cursor))

print(f"Total docs found in DB: {len(docs)}")

# Let's sample descriptions that differ or inspect unique patterns
# Let's inspect length and structure of descriptions
templates = {}
empty_descs = []
for d in docs:
    jid = d["jobId"]
    desc = d.get("description", "")
    if not desc or len(desc.strip()) == 0:
        empty_descs.append(jid)
        continue
    # Let's take the first 150 chars of cleaned text
    soup = BeautifulSoup(desc[:400], "html.parser")
    header = soup.get_text(separator=" ", strip=True)[:100]
    templates[header] = templates.get(header, 0) + 1

print(f"Empty descriptions count: {len(empty_descs)}")
print(f"Top 15 description header patterns:")
for h, count in sorted(templates.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"[{count} jobs] {h}")
