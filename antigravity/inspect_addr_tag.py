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
sample_addr = db.job.find_one({"employerId": emp_id, "jobId": "6abe0fec987a9803d8882c76"})
if sample_addr:
    desc = sample_addr.get("description", "")
    print("=== SAMPLE JOB WITH ADDRESS: 6abe0fec987a9803d8882c76 ===")
    soup = BeautifulSoup(desc, "html.parser")
    for p in soup.find_all("p"):
        if "saddlebrook" in p.get_text().lower():
            print("Found tag:", p)

sample_addr2 = db.job.find_one({"employerId": emp_id, "jobId": "6abe116549b002040d9e814e"})
if sample_addr2:
    desc = sample_addr2.get("description", "")
    print("\n=== SAMPLE JOB WITH ADDRESS: 6abe116549b002040d9e814e ===")
    soup = BeautifulSoup(desc, "html.parser")
    for p in soup.find_all("p"):
        if "bloomfield" in p.get_text().lower():
            print("Found tag:", p)
