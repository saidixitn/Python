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

print(f"Total input IDs: {len(job_ids)}")
print(f"Found in DB: {len(docs)}")

# Let's extract the facility / introductory entity from each job description:
# Patterns:
# 1. "At <Facility>, we do things differently" or "At <Facility>, we are proud"
# 2. "<Facility> has an exciting opportunity" / "<Facility>has an exciting"
# 3. "<Facility> is seeking" / "<Facility>is seeking"
# 4. "in <City>, <State>"
# 5. "<City>, <State>"

extracted = []
for jid in job_ids:
    doc = doc_map.get(jid)
    if not doc:
        extracted.append({"jobId": jid, "status": "NOT_FOUND", "facility_or_loc": "", "title": "", "loc": ""})
        continue
    
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    found_entity = []
    
    # Check "At <Facility>, we"
    m_at = re.findall(r'At\s+([A-Za-z0-9\s.-]+?),\s*we\b', text)
    if m_at:
        found_entity.extend([f"At: {x.strip()}" for x in m_at])
        
    # Check "<Facility> has an exciting" or "<Facility>has an exciting"
    m_has = re.findall(r'([A-Za-z0-9\s.-]{3,40}?)\s*has an exciting opportunity', text, re.IGNORECASE)
    if m_has:
        found_entity.extend([f"Facility: {x.strip()}" for x in m_has])
        
    # Check "<Facility> is seeking" or "<Facility>is seeking"
    m_seeking = re.findall(r'([A-Za-z0-9\s.-]{3,40}?)\s*is seeking a compassionate', text, re.IGNORECASE)
    if m_seeking:
        found_entity.extend([f"Facility: {x.strip()}" for x in m_seeking])
        
    # Check for "Wayland" specifically
    if "wayland" in text.lower():
        found_entity.append("Wayland")
        
    # Check City, State
    cs_m = re.findall(r'\b([A-Z][a-zA-Z\s.-]+?),\s*([A-Z]{2})\b', text)
    for c, s in cs_m:
        c_clean = c.strip()
        if c_clean not in ["Rehab Management", "Management", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"] and len(c_clean) > 2:
            found_entity.append(f"{c_clean}, {s}")
            
    entity_str = "; ".join(list(dict.fromkeys(found_entity)))
    extracted.append({
        "jobId": jid,
        "title": doc.get("title"),
        "location": doc.get("location"),
        "facility_or_loc": entity_str,
        "has_location_or_facility": len(entity_str) > 0,
        "preview": text[:200]
    })

df_res = pd.DataFrame(extracted)
df_res["has_location_or_facility"] = df_res["has_location_or_facility"].fillna(False)
print("\n=== SUMMARY OF 250 USER IDs ===")
print(f"Total: {len(df_res)}")
print(f"Jobs with facility or location in description: {len(df_res[df_res['has_location_or_facility'] == True])}")
print(f"Jobs with NO facility or location in description: {len(df_res[df_res['has_location_or_facility'] == False])}")

# Let's find which ID was not found in DB
not_found = df_res[df_res["status"] == "NOT_FOUND"]["jobId"].tolist()
if not_found:
    print(f"\nJob IDs NOT FOUND in DB: {not_found}")

print("\nSample of jobs with facility or location:")
for r in df_res[df_res['has_location_or_facility']].head(10).to_dict("records"):
    print(f"JobId: {r['jobId']} | LocField: {r['location']} | Entity: {r['facility_or_loc']}")

if len(df_res[~df_res['has_location_or_facility']]) > 0:
    print("\nJobs with NO facility or location at all:")
    for r in df_res[~df_res['has_location_or_facility']].to_dict("records"):
        print(f"JobId: {r['jobId']} | LocField: {r['location']} | Preview: {r['preview']}")

df_res.to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\user_250_qrm_jobs_verified.csv", index=False)
