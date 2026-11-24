from pymongo import MongoClient
import os
import re
from bs4 import BeautifulSoup
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
all_recruiters = set()
all_blocks = set()

def process_desc(desc):
    if not desc or not isinstance(desc, str):
        return
    
    # 1. Emails
    for em in re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', desc):
        all_emails.add(em.strip())
        
    # 2. Phones
    for ph in re.findall(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b', desc):
        all_phones.add(ph.strip())
        
    # 3. Recruiter contact blocks
    soup = BeautifulSoup(desc, 'html.parser')
    text = soup.get_text('\n', strip=True)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    for i, line in enumerate(lines):
        if re.search(r'recruiter\s*contact', line, re.I):
            all_blocks.add(line)
            # following lines often have name, phone, email
            for nxt in lines[i+1:i+5]:
                if '@' in nxt:
                    all_emails.add(nxt)
                elif re.search(r'\d{3}[-.\s]\d{3}', nxt):
                    all_phones.add(nxt)
                elif len(nxt.split()) in [2, 3] and not any(w in nxt.lower() for w in ['inquiries', 'confidential', 'apply', 'opportunity']):
                    all_recruiters.add(nxt)
                    
    # 4. Locations: City, State
    # Look for City, State pattern
    for m in re.finditer(rf'\b([A-Z][a-zA-Z\s.-]+?),\s*({US_STATES})\b', text):
        city = m.group(1).strip()
        state = m.group(2).strip()
        if city not in ["Rehab Management", "Management", "LLC", "Therapy", "Services", "Assistant", "Therapist", "Pathologist", "PTs", "OTs", "SLPs", "COTAs"]:
            # Format: "City, State"
            all_locations.add(f"{city}, {state}")
            all_locations.add(f"{city},{state}")

print("Scanning emp-qrm...")
for doc in emp_qrm.find({}, {"description": 1}).batch_size(1000):
    process_desc(doc.get("description", ""))

print(f"emp-qrm done. Locations so far: {len(all_locations)}, Emails: {len(all_emails)}, Phones: {len(all_phones)}, Recruiters: {len(all_recruiters)}")

print("Scanning Target_P4_Opt...")
for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1}).batch_size(1000):
    process_desc(doc.get("description", ""))

print(f"Target_P4_Opt done. Total Locations: {len(all_locations)}, Emails: {len(all_emails)}, Phones: {len(all_phones)}, Recruiters: {len(all_recruiters)}")

print("\n--- Summary of Found Emails ---")
print(sorted(list(all_emails)))

print("\n--- Summary of Found Phones ---")
print(sorted(list(all_phones)))

print("\n--- Summary of Found Recruiters ---")
print(sorted(list(all_recruiters)))

print("\n--- Sample Locations (First 20) ---")
print(sorted(list(all_locations))[:20])
