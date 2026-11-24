import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from collections import Counter, defaultdict

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
pj_uri = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
pj_client = MongoClient(pj_uri)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"
jobs = list(db.job.find({"employerId": emp_id, "status": "posted"}, {
    "jobId": 1, "title": 1, "location": 1, "description": 1, "clientJobId": 1
}))

print(f"Loaded {len(jobs)} jobs.")

# Let's inspect where street addresses appear
address_regex = re.compile(r'\b\d{2,5}\s+[\w\s\.]+(?:Rd|St|Ave|Blvd|Dr|Hwy|Way|Ln|Pkwy|Circle|Court|Ct|Pl),?\s+[A-Za-z\s]+,?\s+[A-Z]{2}\s+\d{5}', re.IGNORECASE)

addr_found = []
for j in jobs:
    desc = j.get("description", "")
    m = address_regex.findall(desc)
    if m:
        addr_found.append((j["jobId"], j["title"], m))

print(f"\nJobs with physical street addresses in description: {len(addr_found)}")
if addr_found:
    for a in addr_found[:5]:
        print(" ", a[0], a[1], a[2])

# Let's inspect the exact HTML structure at the end of descriptions
tail_patterns = Counter()
for j in jobs:
    desc = j.get("description", "").strip()
    soup = BeautifulSoup(desc, "html.parser")
    tags = soup.find_all(["p", "div", "span", "li", "h1", "h2", "h3"])
    if tags:
        last_tags = " // ".join([t.get_text(strip=True)[:40] for t in tags[-3:]])
        tail_patterns[last_tags] += 1

print("\n--- TOP 10 LAST 3 ELEMENTS IN DESCRIPTIONS ---")
for t, cnt in tail_patterns.most_common(10):
    print(f"[{cnt} jobs] {t}")

# Let's inspect the paragraph with yescommunities.com/Careers
print("\n--- PHRASES WITH CAREERS / URLS ---")
url_paras = Counter()
for j in jobs:
    desc = j.get("description", "")
    soup = BeautifulSoup(desc, "html.parser")
    for p in soup.find_all("p"):
        txt = p.get_text(separator=" ", strip=True)
        if "yescommunities.com" in txt.lower():
            url_paras[txt[:120] + "..."] += 1

for p, cnt in url_paras.most_common(5):
    print(f"[{cnt} jobs] {p}")

# Let's check which titles have the "Posted [Date]" prefix
rx_posted_prefix = re.compile(r'^\s*Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?', re.IGNORECASE)
posted_titles = Counter()
non_posted_titles = Counter()

for j in jobs:
    desc = j.get("description", "")
    if rx_posted_prefix.search(desc):
        posted_titles[j["title"]] += 1
    else:
        non_posted_titles[j["title"]] += 1

print("\n--- TITLES WITH 'Posted [Date]...' AT START ---")
for t, cnt in posted_titles.most_common():
    print(f"  [{cnt} jobs] {t}")

print("\n--- TITLES WITHOUT 'Posted [Date]...' AT START ---")
for t, cnt in non_posted_titles.most_common():
    print(f"  [{cnt} jobs] {t}")
