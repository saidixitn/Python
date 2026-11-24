import os
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(r"./.env")
client = MongoClient(os.getenv("MONGO_URI"))
pj_uri = client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})["mongo_uri"]
pj_client = MongoClient(pj_uri)
db = pj_client["prod_jobiak_ai"]

emp_id = "6a86c3d7060e8f0b78b0dc66"

# Let's inspect a job with the "Posted ..." string
sample_posted = db.job.find_one({"employerId": emp_id, "status": "posted", "description": {"$regex": r"Posted\s+[A-Za-z]+,", "$options": "i"}})
if sample_posted:
    print("=== SAMPLE WITH 'Posted [Day]...' ===")
    print("Job ID:", sample_posted["jobId"])
    print("Title:", sample_posted.get("title"))
    desc = sample_posted["description"]
    # find where "Posted " appears
    idx = desc.lower().find("posted")
    print("\n--- Context around 'Posted': ---")
    start = max(0, idx - 150)
    end = min(len(desc), idx + 250)
    print(desc[start:end])
    print("\n--- First 500 chars of HTML ---")
    print(desc[:500])
    print("\n--- Last 500 chars of HTML ---")
    print(desc[-500:])

# Let's inspect a job with "." opening line
sample_dot = db.job.find_one({"employerId": emp_id, "status": "posted", "description": {"$regex": r"^\s*<[^>]+>\s*\.\s*<", "$options": "i"}})
if not sample_dot:
    sample_dot = db.job.find_one({"employerId": emp_id, "status": "posted", "title": {"$regex": r"Grounds\s*Keeper", "$options": "i"}})
if sample_dot:
    print("\n=== SAMPLE GROUNDS KEEPER ===")
    print("Job ID:", sample_dot["jobId"])
    print("Title:", sample_dot.get("title"))
    print("First 300 chars:")
    print(sample_dot["description"][:300])

# Let's inspect a job with careers url
sample_url = db.job.find_one({"employerId": emp_id, "status": "posted", "description": {"$regex": r"https://www\.yescommunities\.com/Careers", "$options": "i"}})
if sample_url:
    print("\n=== SAMPLE WITH CAREERS URL ===")
    print("Job ID:", sample_url["jobId"])
    print("Title:", sample_url.get("title"))
    desc = sample_url["description"]
    idx = desc.find("https://www.yescommunities.com/Careers")
    start = max(0, idx - 150)
    end = min(len(desc), idx + 250)
    print(desc[start:end])
