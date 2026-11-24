import os
import sys
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
print("Fetching all posted jobs for YES Communities...")
cursor = db.job.find(
    {"employerId": emp_id, "status": "posted"},
    {"jobId": 1, "title": 1, "location": 1, "description": 1, "datePosted": 1, "validThrough": 1, "clientJobId": 1, "url": 1}
)

jobs = list(cursor)
print(f"Total posted jobs fetched: {len(jobs)}")

# Let's inspect descriptions for:
# 1. "Posted" timestamp patterns (e.g. "Posted Wednesday, September 2, 2026, 4:00 AM")
# 2. Requisition/ATS headers
# 3. Dates/Times
# 4. URLs / Apply links
# 5. EEO / Footer boilerplate
# 6. Email addresses / phone numbers

posted_pattern = re.compile(r'Posted\s+[A-Za-z]+,?\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)?', re.IGNORECASE)
general_posted_date = re.compile(r'Posted\s*(?:on|date|at|:)?\s*[:\-]?\s*(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s*)?[A-Za-z]+\s+\d{1,2},?\s+\d{4}', re.IGNORECASE)
time_pattern = re.compile(r'\b\d{1,2}:\d{2}\s*(?:AM|PM)\b', re.IGNORECASE)
req_pattern = re.compile(r'(?:Req(?:uisition)?\s*(?:ID|#|Number)?|Job\s*ID)\s*[:\-]?\s*[\w\d\-]+', re.IGNORECASE)
url_pattern = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
phone_pattern = re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')

matched_posted_exact = []
matched_posted_general = []
matched_times = []
matched_reqs = []
matched_urls = []
matched_emails = []
matched_phones = []

# Also let's check first 300 chars and last 300 chars of plain text
opening_lines = Counter()
closing_lines = Counter()

for j in jobs:
    jid = j["jobId"]
    desc = j.get("description") or ""
    if not desc:
        continue
    
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    if lines:
        opening_lines[lines[0]] += 1
        if len(lines) > 1:
            opening_lines[f"{lines[0]} // {lines[1]}"] += 1
        closing_lines[lines[-1]] += 1

    # Search patterns in desc (both html and text)
    p_exact = posted_pattern.findall(desc)
    if p_exact:
        matched_posted_exact.append((jid, j.get("title"), p_exact))
        
    p_gen = general_posted_date.findall(desc)
    if p_gen:
        matched_posted_general.append((jid, j.get("title"), p_gen))
        
    t_matches = time_pattern.findall(desc)
    if t_matches:
        matched_times.append((jid, j.get("title"), t_matches))
        
    r_matches = req_pattern.findall(desc)
    if r_matches:
        matched_reqs.append((jid, j.get("title"), r_matches))
        
    u_matches = url_pattern.findall(desc)
    if u_matches:
        matched_urls.append((jid, j.get("title"), u_matches))
        
    e_matches = email_pattern.findall(desc)
    if e_matches:
        matched_emails.append((jid, j.get("title"), e_matches))

print("\n--- RESULTS ---")
print(f"Jobs with exact 'Posted [Day], [Month] [Date], [Year]...' matches: {len(matched_posted_exact)}")
if matched_posted_exact:
    for m in matched_posted_exact[:5]:
        print("  Sample:", m[0], m[1], m[2])

print(f"\nJobs with general 'Posted ...' date matches: {len(matched_posted_general)}")
if matched_posted_general:
    for m in matched_posted_general[:5]:
        print("  Sample:", m[0], m[1], m[2])

print(f"\nJobs with isolated time matches (e.g. 4:00 AM): {len(matched_times)}")
if matched_times:
    for m in matched_times[:5]:
        print("  Sample:", m[0], m[1], m[2])

print(f"\nJobs with Req/Job ID in description: {len(matched_reqs)}")
if matched_reqs:
    for m in matched_reqs[:5]:
        print("  Sample:", m[0], m[1], m[2])

print(f"\nJobs with URLs in description: {len(matched_urls)}")
if matched_urls:
    for m in matched_urls[:5]:
        print("  Sample:", m[0], m[1], m[2])

print(f"\nJobs with Emails in description: {len(matched_emails)}")

print("\n--- TOP 10 OPENING TEXT LINES ---")
for line, cnt in opening_lines.most_common(10):
    print(f"[{cnt} jobs] {line[:100]}")

print("\n--- TOP 10 CLOSING TEXT LINES ---")
for line, cnt in closing_lines.most_common(10):
    print(f"[{cnt} jobs] {line[:100]}")
