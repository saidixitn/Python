import os
from collections import Counter, defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
rec = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
pj_client = MongoClient(rec["mongo_uri"], serverSelectionTimeoutMS=8000)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

print("--- 1. RULA_LOCATION_KEYWORDS DEEP DIVE ---")
col_loc = db["rula_location_keywords"]
loc_docs = list(col_loc.find({"employerId": emp_id}))
print(f"Total docs in rula_location_keywords: {len(loc_docs)}")

loc_titles = Counter()
loc_types = Counter()
loc_operators = Counter()
loc_by_title = defaultdict(list)

for d in loc_docs:
    t = d.get("title", "")
    loc_titles[t] += 1
    loc_types[d.get("keywordType", "")] += 1
    loc_operators[d.get("operatorType", "")] += 1
    loc_by_title[t].append(d.get("keyword", ""))

print("Keyword Types in rula_location_keywords:", dict(loc_types))
print("Operator Types in rula_location_keywords:", dict(loc_operators))
print("Titles and counts in rula_location_keywords:")
for t, cnt in loc_titles.most_common():
    print(f"  {t} ({cnt} keywords):")
    sample_kws = loc_by_title[t][:4]
    for kw in sample_kws:
        print(f"    - {kw}")

print("\n--- 2. JOBIAK_KEYWORD_UPDATION DEEP DIVE ---")
col_upd = db["jobiak_keyword_Updation"]
upd_docs = list(col_upd.find({"employerId": emp_id}))
print(f"Total docs in jobiak_keyword_Updation: {len(upd_docs)}")

upd_titles = Counter()
upd_types = Counter()
upd_operators = Counter()
upd_by_title_and_type = defaultdict(lambda: defaultdict(list))

for d in upd_docs:
    t = d.get("title", "")
    ktype = d.get("keywordType", "")
    upd_titles[t] += 1
    upd_types[ktype] += 1
    upd_operators[d.get("operatorType", "")] += 1
    upd_by_title_and_type[t][ktype].append(d.get("keyword", ""))

print("Keyword Types in jobiak_keyword_Updation:", dict(upd_types))
print("Operator Types in jobiak_keyword_Updation:", dict(upd_operators))
print("Titles and counts in jobiak_keyword_Updation:")
for t, cnt in upd_titles.most_common():
    print(f"\n  Title: '{t}' (Total: {cnt} keywords)")
    for kt, kwlist in upd_by_title_and_type[t].items():
        print(f"    [{kt} - {len(kwlist)} keywords]:")
        for kw in kwlist[:3]:
            print(f"      * {kw}")

# Let's check companyName variations
comp_names_loc = set(d.get("companyName") for d in loc_docs)
comp_names_upd = set(d.get("companyName") for d in upd_docs)
print("\nCompany Names in rula_location_keywords:", comp_names_loc)
print("Company Names in jobiak_keyword_Updation:", comp_names_upd)
