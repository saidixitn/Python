import os
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

docs = []
for i in range(0, len(all_ids), 1000):
    batch = all_ids[i:i+1000]
    docs.extend(list(job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1})))

print("Fetched docs:", len(docs))
count = 0
for d in docs:
    desc = d.get("description", "")
    if "wayland, ma" in desc.lower() or "wayland,ma" in desc.lower():
        print("Found JobId:", d["jobId"], "| Location:", d.get("location"))
        soup = BeautifulSoup(desc, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        idx = text.lower().find("wayland")
        print("   Snippet:", text[max(0, idx-80):min(len(text), idx+120)])
        count += 1
        if count >= 3:
            break
