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

# We need regex for City, State in descriptions:
# 1. City, ST: e.g. "Wayland, MA" or "Wayland,MA"
# 2. in <City>, <State> or in <City>,<State>
cs_space_re = re.compile(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}}),\s*({US_STATES})\b')
cs_nospace_re = re.compile(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}}),({US_STATES})\b')

locations_in_desc = set()
recruiter_info = set()

# Recruiter regexes
email_re = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
phone_re = re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
recruiter_header_re = re.compile(r'(?:Recruiter\s*Contact\s*Information:?|Recruiter\s*Contact:?|Recruiter\s*information:?|Recruiter\s*Information:?|Questions\s*before\s*applying\?|How\s*to\s*Apply|For\s*more\s*information,\s*(?:please\s*)?contact:?)', re.I)

def scan_text(desc):
    if not desc:
        return
    
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', ' ', desc)
    
    # Locations
    for m in cs_space_re.finditer(clean):
        c, s = m.group(1).strip(), m.group(2).strip()
        if c not in ["Rehab Management", "Management", "LLC", "Pathologist", "Therapist", "Assistant"]:
            locations_in_desc.add((c, s))
            
    for m in cs_nospace_re.finditer(clean):
        c, s = m.group(1).strip(), m.group(2).strip()
        if c not in ["Rehab Management", "Management", "LLC", "Pathologist", "Therapist", "Assistant"]:
            locations_in_desc.add((c, s))
            
    # Emails
    for em in email_re.findall(desc):
        if "qrm" in em.lower() or "health" in em.lower():
            recruiter_info.add(em.strip())
            
    # Phones
    for ph in phone_re.findall(desc):
        recruiter_info.add(ph.strip())
        
    # Recruiter headers
    for rh in recruiter_header_re.findall(clean):
        recruiter_info.add(rh.strip())

print("Scanning all emp-qrm descriptions...")
for doc in emp_qrm.find({}, {"description": 1}).batch_size(2000):
    scan_text(doc.get("description", ""))

print("Scanning all Target_P4_Opt descriptions for emp-jicn-qrm...")
for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1}).batch_size(2000):
    scan_text(doc.get("description", ""))

print(f"Total Unique City/State pairs found in descriptions: {len(locations_in_desc)}")
print(f"Total Unique Recruiter Info items: {len(recruiter_info)}")

# Also extract the known recruiter names from the recruiter blocks
recruiter_names = [
    "Aryn Chambers",
    "Ana Charles",
    "Ann Webb",
    "Austin Webb",
    "Caitlin Locke",
    "Caitlin",
    "Elizabeth Wall",
    "Jessica Yarger",
    "Kimberly Baugh",
    "Kimberly Dukes-Hartzell",
    "Oralia Gonzalez",
    "Oralia",
    "Paige Reyes, Talent Acquisition Specialist",
    "Paige Reyes",
    "Rebecca Henderson",
    "Stormie Sickles",
    "Tracy LaNeve",
    "Tracy"
]
for n in recruiter_names:
    recruiter_info.add(n)

# Build the replacement list
replacements = []

# 1. Locations
# Sort alphabetically
sorted_locs = sorted(list(locations_in_desc), key=lambda x: (x[0], x[1]))
for c, s in sorted_locs:
    # "City,ST"
    replacements.append({"find": f"{c},{s}", "replace": ""})
    # "City, ST"
    replacements.append({"find": f"{c}, {s}", "replace": ""})
    # Also "in City, ST" and "in City,ST" or "inCity, ST" if needed
    # but the user gave the exact example:
    # {"find": "Wayland,MA", "replace": ""}, {"find": "Wayland, MA", "replace": ""}

# 2. Recruiter info
# Sort recruiter info
for r in sorted(list(recruiter_info)):
    replacements.append({"find": r, "replace": ""})

print(f"Total replacement objects generated: {len(replacements)}")

# Save to JSON
import json
output_path = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_location_recruiter_replacements.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(replacements, f, indent=4)

# Also save formatted exact text as requested by user
txt_output_path = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_replacements_snippet.txt"
with open(txt_output_path, "w", encoding="utf-8") as f:
    for item in replacements:
        f.write('        {\n')
        f.write(f'            "find" : "{item["find"]}",\n')
        f.write(f'            "replace" : "{item["replace"]}"\n')
        f.write('        },\n')

# Copy to artifact directory
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935"
artifact_json = os.path.join(artifact_dir, "qrm_location_recruiter_replacements.json")
with open(artifact_json, "w", encoding="utf-8") as f:
    json.dump(replacements, f, indent=4)

print("Saved successfully to:", output_path)
print("Artifact saved to:", artifact_json)
