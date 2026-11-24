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
    docs.extend(list(job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1})))

print("Total docs fetched:", len(docs))

# Let's inspect all forms of location mentions in descriptions
# Specifically:
# 1. "in <City>, <State>" or "in<City>, <State>" or "<City>, <State>"
# 2. Does description contain any City, State like "Wayland, MA"?

US_STATE_CODES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

# Pattern 1: City, State abbreviation, e.g. "Wayland, MA" or "inWayland, MA" or "Niles, MI" or "Elmwood Park, IL"
# Avoiding false positives like "Rehab Management, LLC", "PTs, OTs", "OTs, SLPs"
city_state_pat = re.compile(r'\b([A-Z][a-zA-Z\s.-]+?),\s*(' + US_STATE_CODES + r')\b')
# Pattern with "in": e.g. "in\s*([A-Z][a-zA-Z\s]+)"
in_city_state_pat = re.compile(r'\bin\s*([A-Za-z\s]+?),\s*(' + US_STATE_CODES + r')\b', re.IGNORECASE)

results = []
false_positives = {"Rehab Management", "Management", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"}

has_loc_count = 0
no_loc_count = 0
no_loc_jobs = []

for d in docs:
    jid = d["jobId"]
    desc = d.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    matches = city_state_pat.findall(text)
    valid_matches = []
    for city, st in matches:
        city_clean = city.strip()
        if city_clean not in false_positives and len(city_clean) > 2 and not any(city_clean.endswith(fp) for fp in ["Therapist", "Assistant"]):
            valid_matches.append(f"{city_clean}, {st}")
            
    # Also check if text contains "in<City>, <State>" without space e.g. "inWayland, MA" or "inNiles, MI"
    no_space_matches = re.findall(r'\bin([A-Z][a-zA-Z\s]+?),\s*(' + US_STATE_CODES + r')\b', text)
    for city, st in no_space_matches:
        city_clean = city.strip()
        if city_clean not in false_positives and len(city_clean) > 2:
            valid_matches.append(f"{city_clean}, {st}")
            
    if valid_matches:
        has_loc_count += 1
    else:
        no_loc_count += 1
        no_loc_jobs.append((jid, d.get("location"), text[:250]))

print(f"Jobs WITH city, state (like Wayland, MA): {has_loc_count}")
print(f"Jobs WITHOUT city, state: {no_loc_count}")

print("\nSample 10 jobs without city, state:")
for jid, loc, prev in no_loc_jobs[:10]:
    print(f"JobId: {jid} | Loc: {loc}")
    print(f"Preview: {prev}\n")
