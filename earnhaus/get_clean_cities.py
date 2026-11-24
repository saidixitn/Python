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

# Let's get all distinct (city, state) from the city and state fields of emp-qrm and Target_P4_Opt
cities_states = set()

for doc in emp_qrm.find({}, {"city": 1, "state": 1}):
    c = doc.get("city")
    s = doc.get("state")
    if c and s and len(s.strip()) == 2:
        c_clean = c.strip().title()
        s_clean = s.strip().upper()
        cities_states.add((c_clean, s_clean))

for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"city": 1, "state": 1}):
    c = doc.get("city")
    s = doc.get("state")
    if c and s and len(s.strip()) == 2:
        c_clean = c.strip().title()
        s_clean = s.strip().upper()
        cities_states.add((c_clean, s_clean))

print(f"Total unique (City, State) from job documents: {len(cities_states)}")

# Also search description for any other City, ST
# A clean city name is 1-3 capitalized words preceding ", ST"
city_pattern = re.compile(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}}),\s*({US_STATES})\b')
city_pattern_nospace = re.compile(rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{0,2}}),({US_STATES})\b')

desc_cities_states = set()
for doc in emp_qrm.find({}, {"description": 1}).limit(2000):
    desc = doc.get("description", "")
    for m in city_pattern.finditer(desc):
        c, s = m.group(1).strip(), m.group(2).strip()
        if c not in ["Rehab Management", "Management", "LLC"]:
            desc_cities_states.add((c.title(), s.upper()))

print(f"Total unique (City, State) from descriptions: {len(desc_cities_states)}")
all_cs = sorted(list(cities_states.union(desc_cities_states)))
print(f"Combined unique (City, State) pairs: {len(all_cs)}")
print("Sample first 15 pairs:", all_cs[:15])
