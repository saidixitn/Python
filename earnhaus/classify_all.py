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

# Check both definitions:
# Def 1: Explicit City, State (like "Wayland, MA" or "Niles, MI")
US_STATE_CODES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'
city_state_pat = re.compile(r'(?:in\s*|[A-Z][a-zA-Z\s.-]+?,\s*)(' + US_STATE_CODES + r')\b')
false_positives = {"Rehab Management, LLC", "PTs, OTs", "OTs, SLPs", "COTAs, SLPs", "COTAs, PTs", "Therapist, OT"}

has_city_state = []
no_city_state = []

# Def 2: Any location or facility name (like Royal Wayland, Nexus at ..., The Fountains at ..., in City, ST)
has_any_loc = []
no_any_loc = []

for d in docs:
    jid = d["jobId"]
    desc = d.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    # check explicit city state
    has_cs = False
    for m in re.finditer(r'\b([A-Z][a-zA-Z\s.-]+?),\s*(' + US_STATE_CODES + r')\b', text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in ["Rehab Management", "Management", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"]:
            has_cs = True
            break
    if not has_cs and re.search(r'\bin\s*([A-Za-z]+),\s*(' + US_STATE_CODES + r')\b', text):
        has_cs = True
        
    if has_cs:
        has_city_state.append(jid)
    else:
        no_city_state.append(jid)
        
    # check any location keyword or facility
    # Notice: "Wayland", "Royal Wayland", "Nexus at", "The Fountains at", "Fountain Care", "James L. West", "Falls Village", "Culver West"
    has_facility_or_loc = has_cs or bool(re.search(r'(?:At\s+Royal|Nexus\s+at|The\s+Fountains\s+at|Fountain\s+Care\s+at|Falls\s+Village|James\s+L\.\s*West|Culver\s+West|The\s+Cedars|River\s+City|Heritage\s+Grove|The\s+Orchards|Royal\s+Oaks)', text, re.IGNORECASE))
    if has_facility_or_loc:
        has_any_loc.append(jid)
    else:
        no_any_loc.append(jid)

print(f"Total jobs: {len(docs)}")
print(f"Jobs with explicit City, State (like 'Wayland, MA'): {len(has_city_state)}")
print(f"Jobs WITHOUT explicit City, State: {len(no_city_state)}")
print(f"Jobs with ANY facility/location mention: {len(has_any_loc)}")
print(f"Jobs with NO facility/location mention: {len(no_any_loc)}")

if no_any_loc:
    print("\nSample no_any_loc previews:")
    for jid in no_any_loc[:5]:
        d = next(x for x in docs if x["jobId"] == jid)
        soup = BeautifulSoup(d.get("description", ""), "html.parser")
        print(jid, soup.get_text(separator=" ", strip=True)[:200])

# Save both lists to CSV/text files so we have them immediately
with open("earnhaus/jobs_without_city_state.txt", "w") as f:
    f.write("\n".join(no_city_state))

with open("earnhaus/jobs_without_any_location.txt", "w") as f:
    f.write("\n".join(no_any_loc))

with open("earnhaus/jobs_with_city_state.txt", "w") as f:
    f.write("\n".join(has_city_state))
