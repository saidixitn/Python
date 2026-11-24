import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mongo_uri = os.getenv("MONGO_URI")
root = MongoClient(mongo_uri)
cred = root["mongo_creds"]["creds"].find_one({"domain": "directclients_prod"})
dc_client = MongoClient(cred["mongo_uri"])
dc_db = dc_client["directclients_prod"]
analytics_col = dc_db["userAnalytics"]
jobs_col = dc_db["Target_P4_Opt"]

emp_id = "emp-jbk-lettuce"

total_ua = analytics_col.count_documents({"employerId": emp_id})
print("Total UA docs:", total_ua)

# Google Views filter
gviews_filter = {
    "employerId": emp_id,
    "isBot": False,
    "browserType": {"$ne": "Unknown"},
    "deviceType": {"$ne": "Unknown"},
    "isFromGoogle": True
}
total_gviews = analytics_col.count_documents(gviews_filter)
print("Total Pure Human Google Views/Clicks:", total_gviews)

# Googlebot visits
bot_filter = {
    "employerId": emp_id,
    "isBot": True
}
total_bot = analytics_col.count_documents(bot_filter)
print("Total Bot Visits:", total_bot)

# Check which job ID field is populated in userAnalytics
sample_ua = analytics_col.find_one(gviews_filter)
print("Sample Google view:", sample_ua)
if sample_ua:
    print("  jobPubJobId:", sample_ua.get("jobPubJobId"))
    print("  childJobId:", sample_ua.get("childJobId"))
    print("  jobId:", sample_ua.get("jobId"))

# Check distinct jobs in Target_P4_Opt
active_posted = jobs_col.count_documents({"employerId": emp_id, "gpost": 5, "job_status": {"$ne": 3}})
print("Active Posted Jobs (gpost:5, job_status!=3):", active_posted)
total_jobs = jobs_col.count_documents({"employerId": emp_id})
print("Total Jobs in Target_P4_Opt:", total_jobs)
