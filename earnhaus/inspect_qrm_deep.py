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

print(f"Total jobs in uploaded CSV: {len(all_ids)}")

docs = []
for i in range(0, len(all_ids), 1000):
    batch = all_ids[i:i+1000]
    docs.extend(list(job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1, "title": 1})))

doc_map = {d["jobId"]: d for d in docs}

# Let's see:
# In QRM job descriptions, what constitutes a location?
# 1. State names or state abbreviations with city: e.g. "Wayland, MA", "Niles, MI", "in Wayland, MA", "in Niles, MI"
# 2. Facility names with location:
#    - "Royal <City/Town>" e.g. "Royal Wayland", "Royal Middletown", "Royal Norwell", "Royal Cotuit", "Royal Megansett", "Royal Westerly", "Royal Braintree"
#    - "Nexus at <City/Town>" e.g. "Nexus at Berwyn", "Nexus at Geneva", "Nexus at Chicago Heights", "Nexus at Elmwood Park"
#    - "The Fountains at <City/Town>" e.g. "The Fountains at Atco"
#    - "Fountain Care at <City/Town>" e.g. "Fountain Care at Sunset Hills"
#    - "The Orchards at <City/Town>" e.g. "The Orchards at Niles"
#    - "Culver West Health Center", "James L. West Alzheimer's Center 1111 Summit Avenue"
#    - Addresses with Street, Drive, Avenue, Road
# 3. Mention of the job's assigned city (e.g. from Location field) or another US city

# Let's inspect descriptions to see which ones have TRULY NO location:
# Neither a City, State, nor a facility name with city/location, nor address, nor city mention.

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

has_location = []
no_location = []

# Known facility/location patterns in QRM descriptions
facility_location_regex = re.compile(
    r'(?:'
    r'Royal\s+(?:Wayland|Middletown|Norwell|Cotuit|Megansett|Westerly|Braintree|Meadow\s*View|Wood\s*Mill|Cape\s*Cod|Sandalwood|Oaks|Health\s*Wayland)|'
    r'Nexus\s+at\s+[A-Za-z\s]+|'
    r'The\s+Fountains\s+at\s+[A-Za-z\s]+|'
    r'Fountain\s+Care\s+at\s+[A-Za-z\s]+|'
    r'The\s+Orchards\s+at\s+[A-Za-z\s]+|'
    r'Culver\s+West|'
    r'James\s+L\.?\s*West|'
    r'Falls\s+Village|'
    r'AVIR\s+at\s+La\s+Hacienda|'
    r'\d{3,5}\s+[A-Z][a-zA-Z\s]+(?:Street|St|Avenue|Ave|Drive|Dr|Road|Rd|Boulevard|Blvd|Lane|Ln|Way|Highway|Hwy)|'
    r'\bin\s*[A-Z][a-zA-Z\s]+,\s*(?:' + state_codes_pat + r')\b|'
    r'\b[A-Z][a-zA-Z\s]{2,20},\s*(?:' + state_codes_pat + r')\b'
    r')',
    re.IGNORECASE
)

# False positive filter for "City, ST" regex
false_positives = {"rehab management, llc", "pts, ots", "ots, slps", "cotas, slps", "cotas, pts", "therapist, ot", "assistant, cota"}

for r in df.to_dict("records"):
    jid = r["jobId"]
    doc = doc_map.get(jid)
    if not doc:
        continue
    
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    # Check for "Wayland" specifically
    has_wayland = "wayland" in text.lower()
    
    # Check facility / location regex
    matches = facility_location_regex.findall(text)
    clean_matches = [m for m in matches if m.lower() not in false_positives]
    
    # Check if assigned city is mentioned in description
    assigned_loc = str(r.get("Location", ""))
    assigned_city = assigned_loc.split(",")[0].strip() if "," in assigned_loc else ""
    city_in_desc = False
    if assigned_city and len(assigned_city) > 3:
        if re.search(r'\b' + re.escape(assigned_city) + r'\b', text, re.IGNORECASE):
            city_in_desc = True
            clean_matches.append(assigned_city)
            
    if clean_matches or has_wayland:
        has_location.append({
            "jobId": jid,
            "title": r.get("Job Title"),
            "location": assigned_loc,
            "detected": "; ".join(list(dict.fromkeys(clean_matches)))
        })
    else:
        no_location.append({
            "jobId": jid,
            "title": r.get("Job Title"),
            "location": assigned_loc,
            "preview": text[:200]
        })

print(f"Total evaluated: {len(doc_map)}")
print(f"Jobs WITH location in description (including Wayland, facilities, city/state): {len(has_location)}")
print(f"Jobs with NO location in description: {len(no_location)}")

if no_location:
    print("\nSample of jobs with NO location in description:")
    for item in no_location[:10]:
        print(f"JobId: {item['jobId']} | Loc: {item['location']} | Title: {item['title']}")
        print(f"Preview: {item['preview']}\n")

# Save the exact CSV
no_loc_ids = set(x["jobId"] for x in no_location)
filtered_df = df[df["jobId"].isin(no_loc_ids)]
out_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_jobs_truly_no_location_in_description.csv"
filtered_df.to_csv(out_csv, index=False)
print(f"Saved {len(filtered_df)} jobs to {out_csv}")

# Also copy to artifacts directory
artifact_csv = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_jobs_truly_no_location_in_description.csv"
filtered_df.to_csv(artifact_csv, index=False)
print(f"Saved artifact copy to {artifact_csv}")
