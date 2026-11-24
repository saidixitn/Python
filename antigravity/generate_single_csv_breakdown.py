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

print("Step 1: Loading job details from prod_jobiak_ai.job...")
all_jobs_cursor = db.job.find(
    {"employerId": emp_id},
    {
        "jobId": 1, "title": 1, "cleansedTitle": 1, "location": 1,
        "locationInfo": 1, "status": 1, "isActive": 1, "datePosted": 1,
        "validThrough": 1, "submittedUrl": 1, "url": 1, "clientJobId": 1, "_id": 0
    }
)

jobs_dict = {}
for j in all_jobs_cursor:
    jid = j.get("jobId")
    if not jid:
        continue
    loc_info = j.get("locationInfo") or {}
    city = loc_info.get("city") or ""
    state = loc_info.get("stageAbbr") or loc_info.get("state") or ""
    if not city and j.get("location"):
        parts = [p.strip() for p in j.get("location", "").split(",")]
        if len(parts) >= 1:
            city = parts[0]
        if len(parts) >= 2:
            state = parts[1]
            
    status_raw = str(j.get("status", "unknown")).strip().lower()
    is_active = bool(j.get("isActive"))
    
    if status_raw == "posted" and is_active:
        status_clean = "Posted"
        active_clean = "Active"
        expired_flag = "NO - Job Still Active (Posted)"
    elif status_raw == "removed" or not is_active:
        status_clean = "Expired"
        active_clean = "Inactive"
        expired_flag = "YES - Job Expired (Removed)"
    else:
        status_clean = status_raw.capitalize()
        active_clean = "Active" if is_active else "Inactive"
        expired_flag = "NO - Job Still Active" if is_active else "YES - Inactive"
        
    jobs_dict[jid] = {
        "jobId": jid,
        "clientJobId": j.get("clientJobId") or "",
        "title": (j.get("title") or "Unknown Title").strip(),
        "location": (j.get("location") or f"{city}, {state}").strip(),
        "city": city or "Unknown",
        "state": state or "Unknown",
        "status": status_clean,
        "isActive": active_clean,
        "expiredFlag": expired_flag,
        "datePosted": j.get("datePosted").strftime("%Y-%m-%d") if j.get("datePosted") else "",
        "validThrough": j.get("validThrough").strftime("%Y-%m-%d") if j.get("validThrough") else "",
        "url": j.get("submittedUrl") or j.get("url") or "",
    }

print(f"Loaded {len(jobs_dict)} jobs.")

print("Step 2: Fetching userAnalytics Google clicks...")
cursor = db.userAnalytics.find(
    {"employerId": emp_id, "isFromGoogle": True, "isBot": False},
    {"jobId": 1, "createdDt": 1, "_id": 0}
).hint("employerId_1")

clicks_10_19 = Counter()
clicks_10_05 = Counter()
clicks_11_17 = Counter()
clicks_11_16 = Counter()
lifetime_clicks = Counter()

for c in cursor:
    dt = c.get("createdDt")
    jid = c.get("jobId")
    if not dt or not jid:
        continue
    d_str = dt.strftime("%Y-%m-%d")
    lifetime_clicks[jid] += 1
    if d_str == "2026-10-19":
        clicks_10_19[jid] += 1
    elif d_str == "2026-10-05":
        clicks_10_05[jid] += 1
    elif d_str == "2026-11-17":
        clicks_11_17[jid] += 1
    elif d_str == "2026-11-16":
        clicks_11_16[jid] += 1

# Union of jobs clicked on max day (10-19 or 10-05) OR yesterday (11-17 or 11-16)
target_job_ids = set(clicks_10_19.keys()) | set(clicks_10_05.keys()) | set(clicks_11_17.keys()) | set(clicks_11_16.keys())
print(f"Total jobs with clicks on Max Day or Yesterday: {len(target_job_ids)}")

rows = []
for jid in target_job_ids:
    jinfo = jobs_dict.get(jid, {
        "jobId": jid,
        "clientJobId": "",
        "title": "Unknown / Deleted Job",
        "location": "Unknown",
        "city": "Unknown",
        "state": "Unknown",
        "status": "Unknown",
        "isActive": "Unknown",
        "expiredFlag": "Unknown",
        "datePosted": "",
        "validThrough": "",
        "url": ""
    })
    
    c_10_19 = clicks_10_19[jid]
    c_10_05 = clicks_10_05[jid]
    c_11_17 = clicks_11_17[jid]
    c_11_16 = clicks_11_16[jid]
    diff_11_17_vs_10_19 = c_11_17 - c_10_19
    diff_11_17_vs_10_05 = c_11_17 - c_10_05
    
    # Impact / Trend Classification
    is_exp = "YES" in jinfo["expiredFlag"]
    if is_exp and c_10_19 > 0:
        impact = f"Lost Due to Job Expiration (Expired {jinfo['validThrough']})"
    elif is_exp and c_10_05 > 0:
        impact = f"Lost Due to Job Expiration (Expired {jinfo['validThrough']})"
    elif is_exp:
        impact = "Expired Job"
    elif c_11_17 > 0 and c_10_19 == 0:
        impact = "New Active Gainer (Clicks gained yesterday)"
    elif c_11_17 > c_10_19:
        impact = "Active Growth (Clicks increased)"
    elif c_11_17 == c_10_19 and c_11_17 > 0:
        impact = "Active Stable (Equal clicks)"
    elif c_11_17 < c_10_19:
        impact = "Active Drop (Organic rank / impression decline)"
    else:
        impact = "Active Job"
        
    row = {
        "Job ID": jid,
        "Job Title": jinfo["title"],
        "Location": jinfo["location"],
        "City": jinfo["city"],
        "State": jinfo["state"],
        "Current Status": jinfo["status"],
        "Active Status": jinfo["isActive"],
        "Is Job Expired?": jinfo["expiredFlag"],
        "Date Posted": jinfo["datePosted"],
        "Valid Through (Expiry Date)": jinfo["validThrough"],
        "Clicks (Max Day 10-19)": c_10_19,
        "Clicks (All-Time Peak 10-05)": c_10_05,
        "Clicks (Yesterday 11-17)": c_11_17,
        "Clicks (Prior Day 11-16)": c_11_16,
        "Clicks Change (Yesterday 11-17 vs Max 10-19)": diff_11_17_vs_10_19,
        "Performance Impact Category": impact,
        "Total Lifetime Clicks": lifetime_clicks[jid],
        "Client Job ID": jinfo["clientJobId"],
        "Job URL": jinfo["url"]
    }
    rows.append(row)

# Sort by Max Day (10-19) desc, Yesterday (11-17) desc, Lifetime desc
df_out = pd.DataFrame(rows)
df_out.sort_values(
    by=["Clicks (Max Day 10-19)", "Clicks (Yesterday 11-17)", "Total Lifetime Clicks"],
    ascending=[False, False, False],
    inplace=True
)

out_file = r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_Max_Day_vs_Yesterday_Job_Clicks_Breakdown.csv"
artifact_file = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6\YES_Communities_Max_Day_vs_Yesterday_Job_Clicks_Breakdown.csv"

df_out.to_csv(out_file, index=False)
df_out.to_csv(artifact_file, index=False)

print(f"Generated CSV with {len(df_out)} job records.")
print(f"Saved to: {out_file}")
print("Top 10 jobs preview:")
print(df_out[["Job ID", "Job Title", "Location", "Is Job Expired?", "Clicks (Max Day 10-19)", "Clicks (Yesterday 11-17)", "Total Lifetime Clicks"]].head(10).to_string())
