import os
import csv
import shutil
import bson
from datetime import datetime
import openpyxl

# Target configuration
EMPLOYER_ID = "6a86c3d7060e8f0b78b0dc66"
COMPANY_NAME = "yes! communities"
CREATED_AT = "2026-11-19T00:00:00.000Z"
CREATED_BY = "tarun.dammu@jobiak.com"
CLASS_NAME = "ai.jobiak.reports.KeywordLocation"

GENERIC_KEYWORDS = [
    "jobs near me",
    "job openings",
    "jobs hiring immediately",
    "jobs hiring",
    "job openings near me",
    "jobs hiring now",
    "job opportunities",
    "hiring near me"
]

# Load workbook
wb_path = r"C:/Users/JOBIAK/Downloads/Keywords - All Clients.xlsx"
wb = openpyxl.load_workbook(wb_path, data_only=False)
ws = wb["Yes Communities"]

# Parse sheet
titles_data = {}
current_title = None

for r in range(1, ws.max_row + 1):
    c1 = ws.cell(row=r, column=1).value
    c3 = ws.cell(row=r, column=3).value
    c5 = ws.cell(row=r, column=5).value
    c7 = ws.cell(row=r, column=7).value
    c8 = ws.cell(row=r, column=8).value
    c9 = ws.cell(row=r, column=9).value

    if c1 and (c3 == "Location Keywords" or (r > 20 and not c3 and any(k in str(c1).lower() for k in ["agent", "manager", "engineer", "technician", "landscaper", "groundskeeper", "coordinator", "administrator"]))):
        raw_title = str(c1).strip()
        current_title = raw_title.lower()
        if current_title not in titles_data:
            titles_data[current_title] = {
                "display_title": raw_title,
                "location": [],
                "company": [],
                "titleToTitle": []
            }

    if current_title:
        if c3 and str(c3).strip() != "Location Keywords":
            kw = str(c3).strip()
            if kw and kw not in titles_data[current_title]["location"]:
                titles_data[current_title]["location"].append(kw)
        if c5 and str(c5).strip() != "Company Keywords":
            kw = str(c5).strip()
            if kw and kw not in titles_data[current_title]["company"]:
                titles_data[current_title]["company"].append(kw)
        for col_val in [c7, c8, c9]:
            if col_val and str(col_val).strip() != "Title-to-Title Keywords":
                kw = str(col_val).strip()
                if kw and kw not in titles_data[current_title]["titleToTitle"]:
                    titles_data[current_title]["titleToTitle"].append(kw)

print(f"Loaded {len(titles_data)} titles from Excel:")
for t, d in titles_data.items():
    print(f"  {t}: loc={len(d['location'])}, comp={len(d['company'])}, t2t={len(d['titleToTitle'])}")

# Build rows for CSV 1: jobiak_keyword_Updation (14 columns)
# Header: _id,employerId,city,state,confidenceValue,keyword,keywordType,operatorType,title,isActive,createdAt,createdBy,_class,companyName
csv1_rows = []

# Build rows for CSV 2: rula_location_keywords (10 columns)
# Header: _id,employerId,confidenceValue,keyword,keywordType,operatorType,title,isActive,companyName,createdAt
csv2_rows = []

for title_lower, d in titles_data.items():
    # 1. genericKeywords (8 per title)
    for gk in GENERIC_KEYWORDS:
        csv1_rows.append([
            str(bson.ObjectId()),
            EMPLOYER_ID,
            "",
            "",
            "0d",
            gk,
            "genericKeywords",
            "equals-title",
            title_lower,
            "true",
            CREATED_AT,
            CREATED_BY,
            CLASS_NAME,
            COMPANY_NAME
        ])
    
    # 2. companyKeywords
    for ck in d["company"]:
        csv1_rows.append([
            str(bson.ObjectId()),
            EMPLOYER_ID,
            "",
            "",
            "0d",
            ck,
            "companyKeywords",
            "equals-title",
            title_lower,
            "true",
            CREATED_AT,
            CREATED_BY,
            CLASS_NAME,
            COMPANY_NAME
        ])

    # 3. titleToTitle
    for tk in d["titleToTitle"]:
        csv1_rows.append([
            str(bson.ObjectId()),
            EMPLOYER_ID,
            "",
            "",
            "0d",
            tk,
            "titleToTitle",
            "equals-title",
            title_lower,
            "true",
            CREATED_AT,
            CREATED_BY,
            CLASS_NAME,
            COMPANY_NAME
        ])

    # 4. locationKeywords -> CSV 2
    for lk in d["location"]:
        csv2_rows.append([
            str(bson.ObjectId()),
            EMPLOYER_ID,
            "0d",
            lk,
            "locationKeywords",
            "equals-title",
            title_lower,
            "true",
            COMPANY_NAME,
            CREATED_AT
        ])

# Write CSV 1
csv1_header = ["_id", "employerId", "city", "state", "confidenceValue", "keyword", "keywordType", "operatorType", "title", "isActive", "createdAt", "createdBy", "_class", "companyName"]
out_csv1 = r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_all_keywords_14col.csv"
with open(out_csv1, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(csv1_header)
    writer.writerows(csv1_rows)

print(f"\nWrote CSV 1 ({len(csv1_rows)} rows) to {out_csv1}")

# Write CSV 2
csv2_header = ["_id", "employerId", "confidenceValue", "keyword", "keywordType", "operatorType", "title", "isActive", "companyName", "createdAt"]
out_csv2 = r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_location_keywords_10col.csv"
with open(out_csv2, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(csv2_header)
    writer.writerows(csv2_rows)

print(f"Wrote CSV 2 ({len(csv2_rows)} rows) to {out_csv2}")

# Copy to brain artifact directory
brain_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
artifact_csv1 = os.path.join(brain_dir, "YES_Communities_all_keywords_14col.csv")
artifact_csv2 = os.path.join(brain_dir, "YES_Communities_location_keywords_10col.csv")

shutil.copyfile(out_csv1, artifact_csv1)
shutil.copyfile(out_csv2, artifact_csv2)
print("Copied files to artifact directory successfully.")
