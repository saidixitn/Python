import os
import re
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from verify_qrm_user_ids import job_ids

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

docs = list(job_col.find({"jobId": {"$in": job_ids}}, {"jobId": 1, "description": 1, "location": 1, "title": 1}))
doc_map = {d["jobId"]: d for d in docs}

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

state_codes_pat = '|'.join(US_STATES.keys())

# Regex specifically for City, State (e.g. "Wayland, MA", "in Niles, MI", "Peabody, MA", etc.)
city_state_regex = re.compile(r'\b([A-Z][a-zA-Z\s.-]+?),\s*(' + state_codes_pat + r')\b')
in_city_state_regex = re.compile(r'\bin\s*([A-Za-z\s]+?),\s*(' + state_codes_pat + r')\b', re.IGNORECASE)

false_positives = {
    "rehab management", "management", "pt", "ot", "pts", "ots", "cota", "cotas", "slp", "slps",
    "therapist", "occupational therapist", "physical therapist", "speech-language pathologist", "assistant"
}

with_city_state = []
without_city_state = []

for jid in job_ids:
    doc = doc_map.get(jid)
    if not doc:
        without_city_state.append({
            "jobId": jid,
            "title": "NOT FOUND",
            "db_location": "NOT FOUND",
            "city_state_matches": "NOT_FOUND_IN_DB",
            "snippet": ""
        })
        continue
    
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    matches = []
    
    # Check "City, ST"
    for m in city_state_regex.finditer(text):
        city, st = m.group(1).strip(), m.group(2)
        if city.lower() not in false_positives and len(city) > 2 and not any(city.lower().endswith(fp) for fp in ["therapist", "assistant", "team"]):
            matches.append(f"{city}, {st}")
            
    # Check "in City, ST"
    for m in in_city_state_regex.finditer(text):
        city, st = m.group(1).strip(), m.group(2)
        if city.lower() not in false_positives and len(city) > 2:
            matches.append(f"{city}, {st}")
            
    matches_unique = list(dict.fromkeys(matches))
    
    if matches_unique:
        # find snippet
        first = matches_unique[0]
        idx = text.find(first)
        snippet = text[max(0, idx-40):min(len(text), idx+80)] if idx != -1 else text[:100]
        with_city_state.append({
            "jobId": jid,
            "title": doc.get("title"),
            "db_location": doc.get("location"),
            "city_state_matches": "; ".join(matches_unique),
            "snippet": snippet
        })
    else:
        without_city_state.append({
            "jobId": jid,
            "title": doc.get("title"),
            "db_location": doc.get("location"),
            "city_state_matches": "None",
            "snippet": text[:120]
        })

print(f"Total IDs: {len(job_ids)}")
print(f"Jobs WITH explicit 'City, State' in description: {len(with_city_state)}")
print(f"Jobs WITHOUT 'City, State' in description: {len(without_city_state)}")

print("\n--- SAMPLE JOBS WITH 'City, State' in description ---")
for r in with_city_state[:5]:
    print(f"JobId: {r['jobId']} | DB Loc: {r['db_location']} | In Desc: {r['city_state_matches']}")
    print(f"  Snippet: {r['snippet']}\n")

print("\n--- SAMPLE JOBS WITHOUT 'City, State' in description ---")
for r in without_city_state[:5]:
    print(f"JobId: {r['jobId']} | DB Loc: {r['db_location']}")
    print(f"  Snippet: {r['snippet']}\n")

# Save both lists to CSV
pd.DataFrame(with_city_state).to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_250_WITH_city_state_in_desc.csv", index=False)
pd.DataFrame(without_city_state).to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_250_WITHOUT_city_state_in_desc.csv", index=False)

# Copy to artifacts
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935"
pd.DataFrame(with_city_state).to_csv(os.path.join(artifact_dir, "qrm_250_WITH_city_state_in_desc.csv"), index=False)
pd.DataFrame(without_city_state).to_csv(os.path.join(artifact_dir, "qrm_250_WITHOUT_city_state_in_desc.csv"), index=False)
