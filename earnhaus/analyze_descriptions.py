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
sample_jobs = df.head(30).to_dict("records")
sample_ids = [r["jobId"] for r in sample_jobs]

docs = list(job_col.find({"jobId": {"$in": sample_ids}}, {"jobId": 1, "description": 1, "location": 1}))
doc_map = {d["jobId"]: d for d in docs}

for r in sample_jobs:
    jid = r["jobId"]
    loc = r.get("Location", "")
    d = doc_map.get(jid)
    if not d:
        continue
    desc = d.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    # Check what user said: "we have locations mentioned in the descriptions like Wayland, MA so ignore those"
    # Let's search for any city/state or location patterns in text
    cs = re.findall(r'[A-Za-z\s]+,\s*[A-Z]{2}\b', text)
    # Also check if the city from loc (e.g. "North Kingstown") or state is in text
    city = loc.split(",")[0].strip() if "," in loc else ""
    state = loc.split(",")[1].strip() if "," in loc and len(loc.split(",")) > 1 else ""
    
    print(f"JID: {jid} | CSV Loc: {loc}")
    print(f"   City in text: {city.lower() in text.lower() if city else False} | State in text: {state.lower() in text.lower() if state else False}")
    if cs:
        print(f"   City, State pattern matches: {cs[:5]}")
    # Print the paragraph mentioning facility / at
    lines = [p.get_text(strip=True) for p in soup.find_all(["p", "li", "div"])]
    facility_lines = [line for line in lines if "royal" in line.lower() or "nexus" in line.lower() or "at " in line.lower() or "location" in line.lower()]
    if facility_lines:
        print(f"   Relevant facility/location lines: {facility_lines[:3]}")
    print("-" * 50)
