import io
import csv
import re
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

csv_text = """Client,EmployerId,jobicare employerId,jobId,clientJobId,Job Title,Location,Submitted URL,Date Posted,Valid Through,Job Views,Title Views,Checked At (UTC)
QRM,6a7b516d060e8f0b78b0dc5a,emp-jicn-qrm,6ad23ae624aec9037efd2efa,language`pathologist`slp`speech~~kingstown`north~~ri~~us~~llc`management`quality`rehab,Speech-Language Pathologist (SLP),"North Kingstown,RI,US",https://qrmhealth.com/gfj/speech-language-pathologist-slp-north-kingstown-ri-6ad23ae624aec9037efd2efa,2026-10-16 14:50:05,2026-11-13 14:50:05,0,20,2026-11-06 06:36:29 UTC
QRM,6a7b516d060e8f0b78b0dc5a,emp-jicn-qrm,6ad23b9024aec9037efd2f20,occupational`ot`therapist~~worcester~~ma~~us~~llc`management`quality`rehab,Occupational Therapist (OT),"Worcester,MA,US",https://qrmhealth.com/gfj/occupational-therapist-ot-worcester-ma-6ad23b9024aec9037efd2f20,2026-10-16 14:50:06,2026-11-13 14:50:06,0,5,2026-11-06 06:36:29 UTC
QRM,6a7b516d060e8f0b78b0dc5a,emp-jicn-qrm,6ad6119578910c03509e0cb9,occupational`ot`therapist~~groton~~ma~~us~~llc`management`quality`rehab,Occupational Therapist (OT),"Groton,MA,US",https://qrmhealth.com/gfj/occupational-therapist-ot-groton-ma-6ad6119578910c03509e0cb9,2026-10-19 00:38:28,2026-11-16 00:38:28,0,5,2026-11-06 06:36:29 UTC
QRM,6a7b516d060e8f0b78b0dc5a,emp-jicn-qrm,6ad7144deb43410385cb87d3,director`dor`house`in`of`rehabilitation~~worcester~~ma~~us~~llc`management`quality`rehab,"Director of Rehabilitation (DOR), In- House","Worcester,MA,US",https://qrmhealth.com/gfj/director-of-rehabilitation-dor-in-house-worcester-ma-6ad7144deb43410385cb87d3,2026-10-20 07:10:31,2026-11-17 07:10:31,0,6,2026-11-06 06:36:29 UTC
QRM,6a7b516d060e8f0b78b0dc5a,emp-jicn-qrm,6adb5dc707e25e03e0c5f974,occupational`ot`therapist~~aurora~~il~~us~~llc`management`quality`rehab,Occupational Therapist (OT),"Aurora,IL,US",https://qrmhealth.com/gfj/occupational-therapist-ot-aurora-il-6adb5dc707e25e03e0c5f974,2026-10-23 00:56:08,2026-11-20 00:56:08,0,5,2026-11-06 06:36:29 UTC
"""

reader = csv.DictReader(io.StringIO(csv_text.strip()))
sample_jobs = list(reader)
job_ids = [r["jobId"] for r in sample_jobs]

print(f"Checking {len(job_ids)} sample jobs...")
docs = list(job_col.find({"jobId": {"$in": job_ids}}, {"jobId": 1, "description": 1, "location": 1, "title": 1}))
print(f"Found {len(docs)} docs.")

for d in docs:
    print("=" * 60)
    print("JobId:", d.get("jobId"))
    print("Location field:", d.get("location"))
    desc = d.get("description", "")
    print("Description length:", len(desc))
    print("Description preview (first 500 chars):")
    print(desc[:500])
