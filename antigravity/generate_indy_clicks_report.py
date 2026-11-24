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

# Load Indianapolis jobs
job_cursor = db.job.find(
    {"employerId": emp_id, "location": {"$regex": "Indianapolis", "$options": "i"}},
    {
        "jobId": 1, "title": 1, "location": 1, "status": 1, "isActive": 1,
        "datePosted": 1, "validThrough": 1, "submittedUrl": 1, "url": 1, "clientJobId": 1
    }
)
indy_jobs = {j["jobId"]: j for j in job_cursor}

analytics_cursor = db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "createdDt": 1, "city": 1, "region": 1, "deviceType": 1, "ipAddress": 1, "_id": 0}
).hint("employerId_1")

clicks = list(analytics_cursor)

# Day-wise clicks for Indianapolis jobs
day_job_clicks = Counter()
day_visitor_clicks = Counter()
day_both_clicks = Counter()

# Detailed records for each click on an Indianapolis job
click_details = []

for c in clicks:
    jid = c.get("jobId")
    dt = c.get("createdDt")
    if not dt:
        continue
    d_str = dt.strftime("%Y-%m-%d")
    v_city = (c.get("city") or "").strip()
    v_region = (c.get("region") or "").strip()
    
    is_indy_job = jid in indy_jobs
    is_indy_visitor = v_city.lower() == "indianapolis"
    
    if is_indy_job:
        day_job_clicks[d_str] += 1
        jinfo = indy_jobs[jid]
        click_details.append({
            "Click Date": d_str,
            "Click Timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "Job ID": jid,
            "Job Title": jinfo.get("title"),
            "Job Location": jinfo.get("location"),
            "Job Status": jinfo.get("status"),
            "Is Active": jinfo.get("isActive"),
            "Visitor City": v_city,
            "Visitor State": v_region,
            "Device Type": c.get("deviceType") or "Unknown",
            "IP Address": c.get("ipAddress") or "",
            "Job URL": jinfo.get("submittedUrl") or jinfo.get("url") or ""
        })
        
    if is_indy_visitor:
        day_visitor_clicks[d_str] += 1
        
    if is_indy_job and is_indy_visitor:
        day_both_clicks[d_str] += 1

# Generate Day-Wise Summary DataFrame
all_dates = sorted(set(day_job_clicks.keys()) | set(day_visitor_clicks.keys()))
daywise_summary = []
for d in all_dates:
    c_job = day_job_clicks[d]
    c_vis = day_visitor_clicks[d]
    c_both = day_both_clicks[d]
    daywise_summary.append({
        "Date": d,
        "Clicks on Indianapolis Jobs (Job Location = Indianapolis,IN,US)": c_job,
        "Clicks from Indianapolis Visitors (Visitor City = Indianapolis)": c_vis,
        "Clicks Both (Indianapolis Job & Visitor)": c_both
    })

df_daywise = pd.DataFrame(daywise_summary)
df_details = pd.DataFrame(click_details)

out_dir = r"c:\Users\JOBIAK\Documents\Python\antigravity"
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"

csv_daywise = os.path.join(out_dir, "YES_Communities_Indianapolis_Clicks_Daywise.csv")
csv_details = os.path.join(out_dir, "YES_Communities_Indianapolis_Job_Clicks_Detailed.csv")

df_daywise.to_csv(csv_daywise, index=False)
df_daywise.to_csv(os.path.join(artifact_dir, "YES_Communities_Indianapolis_Clicks_Daywise.csv"), index=False)

df_details.to_csv(csv_details, index=False)
df_details.to_csv(os.path.join(artifact_dir, "YES_Communities_Indianapolis_Job_Clicks_Detailed.csv"), index=False)

print("Saved CSVs successfully.")
print(f"Total clicks on Indianapolis jobs: {sum(day_job_clicks.values())}")
print(f"Total clicks from Indianapolis visitors: {sum(day_visitor_clicks.values())}")
