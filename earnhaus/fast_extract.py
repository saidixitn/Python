from pymongo import MongoClient
import os
import re
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

emp_qrm = db["emp-qrm"]
target_p4 = db["Target_P4_Opt"]

US_STATES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

all_locations = set()
all_emails = set()
all_phones = set()
all_recruiter_lines = set()

# Precompile regexes
email_re = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
phone_re = re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
city_state_re = re.compile(rf'\b([A-Z][a-zA-Z\s.-]+?),\s*({US_STATES})\b')
city_state_nospace_re = re.compile(rf'\b([A-Z][a-zA-Z\s.-]+?),({US_STATES})\b')
recruiter_re = re.compile(r'(?:recruiter\s*contact\s*information|recruiter\s*contact|recruiter)[^<>\n]*', re.I)

# Also collect distinct city & state fields from documents
field_locations = set()

def scan_collection(coll, query, name):
    print(f"Scanning {name}...")
    cursor = coll.find(query, {"description": 1, "city": 1, "state": 1}).batch_size(2000)
    for doc in cursor:
        c = doc.get("city")
        s = doc.get("state")
        if c and s and len(s) == 2:
            c_clean = c.strip()
            s_clean = s.strip().upper()
            field_locations.add(f"{c_clean}, {s_clean}")
            field_locations.add(f"{c_clean},{s_clean}")

        desc = doc.get("description") or ""
        if not desc:
            continue
        
        # Emails
        for em in email_re.findall(desc):
            all_emails.add(em.strip())
            
        # Phones
        for ph in phone_re.findall(desc):
            all_phones.add(ph.strip())
            
        # Recruiter keywords
        for rec in recruiter_re.findall(desc):
            # clean html
            clean_rec = re.sub(r'<[^>]+>', '', rec).strip()
            if clean_rec:
                all_recruiter_lines.add(clean_rec)
                
        # Regex for city, state in text
        clean_text = re.sub(r'<[^>]+>', ' ', desc)
        for m in city_state_re.finditer(clean_text):
            city = m.group(1).strip()
            state = m.group(2).strip()
            if city not in ["Rehab Management", "Management", "LLC", "Therapy", "Services", "Assistant", "Therapist", "Pathologist", "PTs", "OTs", "SLPs", "COTAs"]:
                all_locations.add(f"{city}, {state}")
                all_locations.add(f"{city},{state}")
                
        for m in city_state_nospace_re.finditer(clean_text):
            city = m.group(1).strip()
            state = m.group(2).strip()
            if city not in ["Rehab Management", "Management", "LLC", "Therapy", "Services", "Assistant", "Therapist", "Pathologist", "PTs", "OTs", "SLPs", "COTAs"]:
                all_locations.add(f"{city}, {state}")
                all_locations.add(f"{city},{state}")

scan_collection(emp_qrm, {}, "emp-qrm")
scan_collection(target_p4, {"employerId": "emp-jicn-qrm"}, "Target_P4_Opt")

print("\n--- RESULTS ---")
print(f"Total Unique Locations from text & fields: {len(all_locations.union(field_locations))}")
print(f"Total Unique Emails: {len(all_emails)}")
print(f"Total Unique Phones: {len(all_phones)}")
print(f"Total Unique Recruiter phrases: {len(all_recruiter_lines)}")

# Save intermediate results
with open(r"c:\Users\JOBIAK\Documents\Python\earnhaus\extracted_locations.txt", "w", encoding="utf-8") as f:
    for loc in sorted(list(all_locations.union(field_locations))):
        f.write(loc + "\n")

with open(r"c:\Users\JOBIAK\Documents\Python\earnhaus\extracted_recruiter.txt", "w", encoding="utf-8") as f:
    f.write("=== EMAILS ===\n")
    for em in sorted(list(all_emails)):
        f.write(em + "\n")
    f.write("\n=== PHONES ===\n")
    for ph in sorted(list(all_phones)):
        f.write(ph + "\n")
    f.write("\n=== RECRUITER PHRASES ===\n")
    for r in sorted(list(all_recruiter_lines)):
        f.write(r + "\n")

print("Files saved successfully!")
