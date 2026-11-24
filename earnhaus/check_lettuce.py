from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "directclients_prod"})
client = MongoClient(creds["mongo_uri"])
db = client["directclients_prod"]
p4 = db["Target_P4_Opt"]

query = {"employerId": "emp-jbk-lettuce", "gpost": 5}
projection = {
    "employerId": 1,
    "jobtitle": 1,
    "location": 1,
    "locationKeywords": 1,
    "submittedUrl": 1
}

docs = list(p4.find(query, projection))
print(f"Total matching docs with gpost=5: {len(docs)}")

# Also check without gpost filter to see total lettuce jobs
total_lettuce = p4.count_documents({"employerId": "emp-jbk-lettuce"})
print(f"Total lettuce docs in Target_P4_Opt: {total_lettuce}")

# Check distinct gpost values for emp-jbk-lettuce
gpost_vals = p4.distinct("gpost", {"employerId": "emp-jbk-lettuce"})
print("Distinct gpost values:", gpost_vals)

# Inspect a few docs with {city} or {state} in locationKeywords
needs_update = []
for d in docs:
    lkw = d.get("locationKeywords")
    if isinstance(lkw, list):
        has_placeholder = any("{city}" in str(k) or "{state}" in str(k) for k in lkw)
        if has_placeholder:
            needs_update.append(d)

print(f"Docs with gpost=5 that have {{city}} or {{state}} placeholders in locationKeywords: {len(needs_update)}")

if needs_update:
    print("\nSample doc needing update:")
    sample = needs_update[0]
    print("  Title:", sample.get("jobtitle"))
    print("  Location:", sample.get("location"))
    print("  SubmittedUrl:", sample.get("submittedUrl"))
    print("  LocationKeywords:", sample.get("locationKeywords"))
