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

print(f"Fetching {len(all_ids)} docs...")
docs = []
for i in range(0, len(all_ids), 1000):
    batch = all_ids[i:i+1000]
    cursor = job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1, "title": 1})
    docs.extend(list(cursor))

doc_map = {d["jobId"]: d for d in docs}
print(f"Found {len(docs)} docs.")

# US State abbreviations and full names
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

# Also let's check for "City, ST" patterns
city_state_regex = re.compile(r'\b[A-Z][a-zA-Z\s.-]+,\s*(' + '|'.join(US_STATES.keys()) + r')\b')
zip_regex = re.compile(r'\b\d{5}(?:-\d{4})?\b')

# Check each job
no_loc_jobs = []
has_city_state_pattern = []
has_assigned_city = []
other_loc_jobs = []

for r in all_records:
    jid = r["jobId"]
    csv_loc = str(r.get("Location", ""))
    doc = doc_map.get(jid)
    if not doc:
        continue
    
    desc_html = doc.get("description", "")
    soup = BeautifulSoup(desc_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    parts = [p.strip() for p in csv_loc.split(",") if p.strip()]
    city = parts[0] if len(parts) > 0 else ""
    state_code = parts[1] if len(parts) > 1 else ""
    state_full = US_STATES.get(state_code, "")
    
    # Check if city is mentioned in description (case insensitive, whole word)
    city_in_desc = False
    if city and len(city) > 2:
        if re.search(r'\b' + re.escape(city) + r'\b', text, re.IGNORECASE):
            city_in_desc = True
            
    # Check if any "City, ST" is in description
    cs_match = city_state_regex.findall(text)
    
    # Check zip
    has_zip = bool(zip_regex.search(text))
    
    if cs_match or city_in_desc:
        has_assigned_city.append(jid)
    else:
        no_loc_jobs.append({
            "jobId": jid,
            "title": r.get("Job Title"),
            "csv_loc": csv_loc,
            "preview": text[:200]
        })

print(f"Jobs with city or City, ST pattern: {len(has_assigned_city)}")
print(f"Jobs without city or City, ST pattern: {len(no_loc_jobs)}")

# Print sample of no_loc_jobs
print("\nSample of jobs without city/City, ST pattern:")
for item in no_loc_jobs[:10]:
    print(f"JobId: {item['jobId']} | CSV Loc: {item['csv_loc']} | Title: {item['title']}")
    print(f"Preview: {item['preview']}\n")
