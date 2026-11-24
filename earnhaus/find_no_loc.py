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

docs = []
for i in range(0, len(all_ids), 1000):
    batch = all_ids[i:i+1000]
    cursor = job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1, "title": 1})
    docs.extend(list(cursor))

doc_map = {d["jobId"]: d for d in docs}

# Let's inspect all matches of "At Royal [A-Za-z ]+", "Nexus at [A-Za-z ]+", "at [A-Za-z ]+", etc.
facility_names = set()
no_facility_or_loc = []

# Common patterns for facilities in QRM descriptions:
# "At Royal [Facility]"
# "Nexus at [Facility]"
# "[Facility] SNF"
# "[Facility] Nursing"
# "[Facility] Health"
# "[Facility] Center"
# "[Facility] Rehabilitation"

for d in docs:
    jid = d["jobId"]
    desc = d.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    # Let's check for facility intro phrases
    # "At Royal <Name>" or "At <Name>" or "Nexus at <Name>"
    m_royal = re.findall(r'At\s+Royal\s+([A-Za-z\s]+?)(?:,|\.|\bwe\b|\bNursing\b|\bHealth\b|\bCenter\b)', text, re.IGNORECASE)
    m_nexus = re.findall(r'Nexus\s+at\s+([A-Za-z\s]+?)(?:,|\.|\bhas\b|\bis\b|\bSNF\b)', text, re.IGNORECASE)
    m_fountains = re.findall(r'The\s+Fountains\s+at\s+([A-Za-z\s]+?)(?:,|\.|\bhas\b|\bis\b|\bSNF\b)', text, re.IGNORECASE)
    
    # Also check if text has any general location indicators
    # e.g., "Location:", "Address:", "Wayland", "MA", etc.
    
    has_any_mention = False
    if m_royal or m_nexus or m_fountains:
        has_any_mention = True
        for name in m_royal + m_nexus + m_fountains:
            clean_name = name.strip()
            if len(clean_name) > 2 and len(clean_name) < 30:
                facility_names.add(clean_name)
    else:
        # Check other phrases
        m_other = re.findall(r'At\s+([A-Z][a-zA-Z\s]{2,25}?)(?:,|\.|\bwe\b)', text)
        if m_other:
            # check if it looks like a facility
            for o in m_other:
                if any(k in o.lower() for k in ["center", "nursing", "rehab", "villa", "home", "village", "manor"]):
                    has_any_mention = True
                    facility_names.add(o.strip())
        
        # Check if first 300 chars mention a facility
        intro = text[:300]
        if any(k in intro.lower() for k in ["health center", "alzheimer", "rehabilitation and wellness", "snf", "nursing and rehab"]):
            has_any_mention = True

    if not has_any_mention:
        no_facility_or_loc.append((jid, text[:300]))

print(f"Total jobs evaluated: {len(docs)}")
print(f"Sample facilities found: {list(facility_names)[:25]}")
print(f"Count of jobs with NO facility / location detected: {len(no_facility_or_loc)}")
if no_facility_or_loc:
    print("\nFirst 10 jobs with NO facility / location:")
    for jid, prev in no_facility_or_loc[:10]:
        print(f"JobId: {jid}")
        print(f"Text preview: {prev}\n")
