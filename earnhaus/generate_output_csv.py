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
    docs.extend(list(job_col.find({"jobId": {"$in": batch}}, {"jobId": 1, "description": 1, "location": 1, "title": 1})))

doc_map = {d["jobId"]: d for d in docs}

US_STATE_CODES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'
city_state_pat = re.compile(r'\b([A-Z][a-zA-Z\s.-]+?),\s*(' + US_STATE_CODES + r')\b')
in_pat = re.compile(r'\bin\s*([A-Za-z\s]+?),\s*(' + US_STATE_CODES + r')\b', re.IGNORECASE)

false_positives = {"Rehab Management", "Management", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"}

records = []
no_location_ids = []

for r in df.to_dict("records"):
    jid = r["jobId"]
    doc = doc_map.get(jid)
    if not doc:
        continue
    
    desc = doc.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    detected = []
    for m in city_state_pat.finditer(text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in false_positives and len(c) > 2 and not any(c.endswith(fp) for fp in ["Therapist", "Assistant"]):
            detected.append(f"{c}, {s}")
            
    for m in in_pat.finditer(text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in false_positives and len(c) > 2:
            detected.append(f"{c}, {s}")
            
    detected_unique = list(dict.fromkeys(detected))
    has_loc = len(detected_unique) > 0
    
    if not has_loc:
        no_location_ids.append(jid)
        
    records.append({
        "jobId": jid,
        "Job Title": r.get("Job Title"),
        "DB Location": doc.get("location"),
        "Has Location in Description": "YES" if has_loc else "NO",
        "Detected Location in Description": "; ".join(detected_unique) if has_loc else ""
    })

out_df = pd.DataFrame(records)
out_df.to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_jobs_location_validation.csv", index=False)

no_loc_df = out_df[out_df["Has Location in Description"] == "NO"]
no_loc_df[["jobId", "Job Title", "DB Location"]].to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_jobs_NO_location_in_description.csv", index=False)

with open(r"c:\Users\JOBIAK\Documents\Python\earnhaus\no_location_job_ids.txt", "w") as f:
    f.write("\n".join(no_location_ids))

print(f"Total processed: {len(records)}")
print(f"Jobs WITH location in description (like Wayland, MA): {len(records) - len(no_location_ids)}")
print(f"Jobs WITHOUT location in description: {len(no_location_ids)}")
