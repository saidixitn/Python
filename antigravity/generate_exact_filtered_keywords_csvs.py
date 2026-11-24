import os
import csv
import shutil
import bson

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

COMPANY_KEYWORDS = {
    "resident activities coordinator": [
        "Activities Coordinator jobs at YES Communities",
        "YES Communities jobs",
        "YES Communities jobs near me",
        "work at YES Communities"
    ],
    "office administrator": [
        "Office Administrator jobs at YES Communities",
        "YES Communities Administrative Assistant jobs",
        "YES Communities hiring Office Administrator",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "sales & leasing agent": [
        "YES Communities Leasing Agent jobs",
        "YES Communities Sales jobs",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "community manager-in-training": [
        "Community Manager jobs at YES Communities",
        "YES Communities Community Manager jobs",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "community manager": [
        "Community Manager jobs at YES Communities",
        "YES Communities Community Manager jobs",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "senior data engineer": [
        "Data Engineer jobs at YES Communities",
        "YES Communities hiring Data Engineer",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "groundskeeper": [
        "YES Communities Groundskeeper jobs",
        "YES Communities Landscaper jobs",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "seasonal landscaper": [
        "Landscaping jobs at YES Communities",
        "YES Communities Landscaping jobs",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "maintenance technician": [
        "YES Communities Maintenance jobs",
        "YES Communities hiring Maintenance Technician",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ],
    "residential maintenance technician": [
        "Maintenance Technician jobs at YES Communities",
        "YES Communities Maintenance jobs",
        "YES Communities jobs",
        "YES Communities jobs near me"
    ]
}

# Parse the user-provided file
source_path = r"c:\Users\JOBIAK\Documents\Python\antigravity\user_provided_filtered_keywords.csv"
with open(source_path, "r", encoding="utf-8") as f:
    rows = list(csv.reader(f))

current_title = None
title_data = {}

for r in rows:
    non_empty = [c.strip() for c in r if c.strip()]
    if not non_empty:
        continue
    c0 = r[0].strip()
    if c0:
        current_title = c0.lower()
        title_data[current_title] = {
            "title_to_title": [],
            "location": []
        }
    elif current_title:
        line_str = " ".join(non_empty).lower()
        if "city" in line_str and "state" in line_str:
            for item in non_empty:
                # normalize 'in city state' to 'in city, state'
                norm_item = item
                if "in city state" in norm_item:
                    norm_item = norm_item.replace("in city state", "in city, state")
                if norm_item not in title_data[current_title]["location"]:
                    title_data[current_title]["location"].append(norm_item)
        else:
            # titleToTitle
            for item in non_empty:
                if item not in title_data[current_title]["title_to_title"]:
                    title_data[current_title]["title_to_title"].append(item)

print(f"Parsed {len(title_data)} titles:")
for t, d in title_data.items():
    print(f"  {t}: t2t={len(d['title_to_title'])}, loc={len(d['location'])}")

# Build CSV 1: jobiak_keyword_Updation (14 columns)
# Header: _id,employerId,city,state,confidenceValue,keyword,keywordType,operatorType,title,isActive,createdAt,createdBy,_class,companyName
csv1_rows = []

# Build CSV 2: rula_location_keywords (10 columns)
# Header: _id,employerId,confidenceValue,keyword,keywordType,operatorType,title,isActive,companyName,createdAt
csv2_rows = []

for title_lower, d in title_data.items():
    # 1. Generic keywords
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

    # 2. Company keywords
    comp_list = COMPANY_KEYWORDS.get(title_lower, [
        "YES Communities jobs",
        "YES Communities jobs near me"
    ])
    for ck in comp_list:
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

    # 3. titleToTitle keywords
    for tk in d["title_to_title"]:
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

    # 4. Location keywords
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
out_csv1 = r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_New_Keywords_All_14col.csv"
with open(out_csv1, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(csv1_header)
    writer.writerows(csv1_rows)

print(f"\nWrote CSV 1 ({len(csv1_rows)} rows) to {out_csv1}")

# Write CSV 2
csv2_header = ["_id", "employerId", "confidenceValue", "keyword", "keywordType", "operatorType", "title", "isActive", "companyName", "createdAt"]
out_csv2 = r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_New_Keywords_Location_10col.csv"
with open(out_csv2, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(csv2_header)
    writer.writerows(csv2_rows)

print(f"Wrote CSV 2 ({len(csv2_rows)} rows) to {out_csv2}")

# Mirror to Artifact directory
brain_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"
artifact_csv1 = os.path.join(brain_dir, "YES_Communities_New_Keywords_All_14col.csv")
artifact_csv2 = os.path.join(brain_dir, "YES_Communities_New_Keywords_Location_10col.csv")

shutil.copyfile(out_csv1, artifact_csv1)
shutil.copyfile(out_csv2, artifact_csv2)
print("Mirrored both CSVs to artifact directory.")
