from pymongo import MongoClient
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "directclients_prod"})
client = MongoClient(creds["mongo_uri"])
db = client["directclients_prod"]
p4 = db["Target_P4_Opt"]

query = {"employerId": "emp-jbk-lettuce", "gpost": 5}
docs = list(p4.find(query, {
    "_id": 1,
    "jobtitle": 1,
    "location": 1,
    "locationKeywords": 1,
    "submittedUrl": 1,
    "city": 1,
    "state": 1
}))

needs_update = []
loc_lengths = set()

for d in docs:
    lkw = d.get("locationKeywords")
    if isinstance(lkw, list) and any("{city}" in str(k) or "{state}" in str(k) for k in lkw):
        needs_update.append(d)
        loc = d.get("location", "")
        loc_lengths.add(len(lkw))

print(f"Total needing update: {len(needs_update)}")
print(f"Keyword list lengths found: {loc_lengths}")

# Check location format
sample_locs = set(d.get("location", "") for d in needs_update)
print(f"Unique location strings in these docs: {len(sample_locs)}")
print("Sample locations:", list(sample_locs)[:10])

# Check if city and state fields are already present on docs
has_city_field = sum(1 for d in needs_update if d.get("city"))
has_state_field = sum(1 for d in needs_update if d.get("state"))
print(f"Docs with explicit 'city' field: {has_city_field} / {len(needs_update)}")
print(f"Docs with explicit 'state' field: {has_state_field} / {len(needs_update)}")
