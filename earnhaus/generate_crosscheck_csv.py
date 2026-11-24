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

records = []
for jid in job_ids:
    doc = doc_map.get(jid)
    if not doc:
        records.append({
            "jobId": jid,
            "Job Title": "NOT FOUND IN DB",
            "DB Location": "NOT FOUND",
            "Has Location / Facility in Description": "NO (NOT FOUND)",
            "Detected Location / Facility in Description": "Job ID does not exist in prod_jobiak_ai.job",
            "Description Snippet": ""
        })
        continue
    
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    found = []
    
    # Check for "Wayland"
    if "wayland" in text.lower():
        found.append("Wayland")
        
    # Check facility intro: "At Royal...", "At Embassy...", etc.
    m_at = re.findall(r'At\s+([A-Za-z0-9\s.-]+?),\s*we\b', text)
    if m_at:
        found.extend([f"Facility: {x.strip()}" for x in m_at])
        
    m_has = re.findall(r'([A-Za-z0-9\s.-]{3,40}?)\s*has an exciting opportunity', text, re.IGNORECASE)
    if m_has:
        found.extend([f"Facility: {x.strip()}" for x in m_has])
        
    m_seeking = re.findall(r'([A-Za-z0-9\s.-]{3,40}?)\s*is seeking a compassionate', text, re.IGNORECASE)
    if m_seeking:
        found.extend([f"Facility: {x.strip()}" for x in m_seeking])
        
    # Kingwood or other facility keywords
    if "kingwood" in text.lower():
        found.append("Facility: Kingwood Rehab")
        
    # Check City, State
    cs_m = re.findall(r'\b([A-Z][a-zA-Z\s.-]+?),\s*([A-Z]{2})\b', text)
    for c, s in cs_m:
        c_clean = c.strip()
        if c_clean not in ["Rehab Management", "Management", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"] and len(c_clean) > 2:
            found.append(f"{c_clean}, {s}")
            
    # Check assigned city
    loc_val = doc.get("location", "")
    city = loc_val.split(",")[0].strip() if "," in loc_val else ""
    if city and len(city) > 3:
        if re.search(r'\b' + re.escape(city) + r'\b', text, re.IGNORECASE):
            found.append(f"City: {city}")
            
    found_unique = list(dict.fromkeys(found))
    has_loc = len(found_unique) > 0
    
    # Grab the relevant snippet around the detected facility / location
    snippet = ""
    if found_unique:
        first_term = found_unique[0].split(":")[-1].strip().split(",")[0].strip()
        idx = text.lower().find(first_term.lower())
        if idx != -1:
            snippet = text[max(0, idx - 40):min(len(text), idx + 100)]
    if not snippet:
        snippet = text[:120]
        
    records.append({
        "jobId": jid,
        "Job Title": doc.get("title"),
        "DB Location": loc_val,
        "Has Location / Facility in Description": "YES" if has_loc else "NO",
        "Detected Location / Facility in Description": "; ".join(found_unique) if has_loc else "None",
        "Description Snippet": snippet
    })

out_df = pd.DataFrame(records)
out_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_250_crosscheck_results.csv"
out_df.to_csv(out_csv, index=False)

artifact_csv = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_250_crosscheck_results.csv"
out_df.to_csv(artifact_csv, index=False)

print("Saved crosscheck CSV to:")
print(" -", out_csv)
print(" -", artifact_csv)
