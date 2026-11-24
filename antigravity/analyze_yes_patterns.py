import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from collections import Counter, defaultdict
import pandas as pd

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
pj_uri = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
pj_client = MongoClient(pj_uri)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"
jobs = list(db.job.find({"employerId": emp_id, "status": "posted"}, {"jobId": 1, "title": 1, "location": 1, "description": 1, "datePosted": 1, "validThrough": 1, "clientJobId": 1}))

print(f"Loaded {len(jobs)} posted jobs.")

# Let's inspect the exact prefixes of descriptions
prefix_patterns = Counter()
posted_at_start = []
posted_anywhere = []
stray_dot_start = []
has_careers_url = []
has_pay_rate_block = []
has_trailing_address = []
other_date_patterns = []

# Regex patterns
rx_posted_prefix = re.compile(r'^\s*Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?', re.IGNORECASE)
rx_posted_any = re.compile(r'Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?', re.IGNORECASE)
rx_dot_prefix = re.compile(r'^\s*<p><strong>\s*\.\s*</strong></p>', re.IGNORECASE)
rx_pay_block = re.compile(r'<p><strong>Pay Type:</strong>.*?</p>', re.DOTALL | re.IGNORECASE)
rx_address_tail = re.compile(r'<p>(?:\d{1,5}\s+[\w\s\.]+(?:Rd|St|Ave|Blvd|Dr|Hwy|Way|Ln|Pkwy|Circle|Court|Ct|Pl),?\s+[A-Za-z\s]+,?\s+[A-Z]{2}\s+\d{5}(?:-\d{4})?,?\s*(?:USA|United States)?)</p>\s*$', re.IGNORECASE)

date_time_samples = []

for j in jobs:
    jid = j["jobId"]
    desc = j.get("description", "")
    
    # Check posted prefix
    m_pref = rx_posted_prefix.search(desc)
    if m_pref:
        posted_at_start.append({
            "jobId": jid,
            "title": j["title"],
            "matched_text": m_pref.group(0).strip(),
            "location": j.get("location", "")
        })
    
    m_any = rx_posted_any.findall(desc)
    if m_any:
        posted_anywhere.append((jid, m_any))
        date_time_samples.extend(m_any)
        
    m_dot = rx_dot_prefix.search(desc)
    if m_dot:
        stray_dot_start.append(jid)
        
    if "https://www.yescommunities.com/Careers" in desc or "yescommunities.com/careers" in desc:
        has_careers_url.append(jid)
        
    if rx_pay_block.search(desc):
        has_pay_rate_block.append(jid)
        
    if rx_address_tail.search(desc):
        has_trailing_address.append(jid)

print(f"\n1. Jobs with 'Posted [Day], [Date], [Time]' at START of description: {len(posted_at_start)}")
print(f"2. Jobs with 'Posted [Day], [Date], [Time]' ANYWHERE in description: {len(posted_anywhere)}")
print(f"3. Jobs starting with stray dot `<p><strong>.</strong></p>`: {len(stray_dot_start)}")
print(f"4. Jobs containing 'yescommunities.com/careers' URL: {len(has_careers_url)}")
print(f"5. Jobs containing trailing Pay Type / Min / Max Rate HTML block: {len(has_pay_rate_block)}")
print(f"6. Jobs containing trailing street address in HTML: {len(has_trailing_address)}")

# Let's inspect unique sample timestamps from posted_at_start
print("\nUnique Date/Time strings found in 'Posted ...' headers (top 15):")
dt_counts = Counter([x["matched_text"] for x in posted_at_start])
for txt, cnt in dt_counts.most_common(15):
    print(f"  [{cnt} jobs] '{txt}'")

# Let's check descriptions that DO NOT start with 'Posted ...' - what do they start with?
non_posted = [j for j in jobs if not rx_posted_prefix.search(j.get("description", ""))]
print(f"\nJobs NOT starting with 'Posted ...': {len(non_posted)}")
non_posted_starts = Counter()
for j in non_posted:
    desc = j.get("description", "").strip()
    soup = BeautifulSoup(desc[:200], "html.parser")
    first_p = soup.find(["p", "div", "h1", "h2", "h3", "strong"])
    text_snippet = first_p.get_text(strip=True) if first_p else desc[:50]
    non_posted_starts[text_snippet[:60]] += 1

print("Top starting elements in non-posted jobs:")
for snip, cnt in non_posted_starts.most_common(10):
    print(f"  [{cnt} jobs] '{snip}'")
