import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
analytics = db["userAnalytics"]
jobs_col = db["job"]

# Sample isBot: True document
sample_bot = analytics.find_one({"employerId": emp_id, "isBot": True})
print("Sample Bot Doc:")
for k, v in (sample_bot or {}).items():
    print(f"  {k}: {v}")

# Distinct jobs with bot
bot_job_ids = analytics.distinct("childJobId", {
    "employerId": emp_id,
    "isBot": True,
    "country": "United States"
})
print(f"\nDistinct childJobId with Googlebot (US, isBot:True): {len(bot_job_ids)}")

all_bot_job_ids = analytics.distinct("childJobId", {
    "employerId": emp_id,
    "isBot": True
})
print(f"Distinct childJobId with any isBot:True: {len(all_bot_job_ids)}")

# Posted jobs
posted_jobs = list(jobs_col.find(
    {"employerId": emp_id, "status": "posted", "isActive": True},
    {"_id": 0, "jobId": 1, "clientJobId": 1, "title": 1, "location": 1, "datePosted": 1}
))
print(f"Total posted jobs: {len(posted_jobs)}")

# Posted jobs with NO bot
posted_job_ids = {j["jobId"] for j in posted_jobs if j.get("jobId")}
posted_with_no_bot = posted_job_ids - set(bot_job_ids)
print(f"Posted jobs with NO US Googlebot: {len(posted_with_no_bot)}")
posted_with_no_bot_all = posted_job_ids - set(all_bot_job_ids)
print(f"Posted jobs with NO bot at all: {len(posted_with_no_bot_all)}")
