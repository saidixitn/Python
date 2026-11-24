import os
import re
import time
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# Connect to jobicarenode_prod
jic_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jic_client = MongoClient(jic_creds["mongo_uri"])
target_col = jic_client["jobicarenode_prod"]["Target_P4_Opt"]

# Connect to prod_jobiak_ai
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

# Pipeline requested by user
pipeline = [
    {
        "$match": {
            "employerId": "emp-jicn-qrm",
            "job_status": {"$ne": 3},
            "gpost": 3,
            "jobtitle": {
                "$in": [
                    "Physical Therapist Assistant (PTA)",
                    "Certified Occupational Therapy Assistant (COTA)",
                    "Speech-Language Pathologist (SLP)",
                    "Occupational Therapist (OT)",
                    "Physical Therapist (PT)",
                ]
            },
            "salary_feed": {"$ne": "$0 - $0"}
        }
    },
    {
        "$group": {
            "_id": "$uniqueKey",
            "doc": {"$first": "$$ROOT"}
        }
    },
    {
        "$replaceRoot": {
            "newRoot": "$doc"
        }
    },
    {
        "$sample": {
            "size": 20000
        }
    },
    {
        "$group": {
            "_id": "$jobtitle",
            "docs": {
                "$push": {
                    "_id": "$uniqueKey",
                    "company": "$company",
                    "employerId": "$employerId",
                    "jobtitle": "$jobtitle",
                    "location": "$location",
                    "clientJobId": "$clientJobId",
                    "jobId": "$jobId",
                    "jobdescription_opt": "$jobdescription_opt"
                }
            }
        }
    },
    {
        "$project": {
            "title": "$_id",
            "docs": 1,
            "count": {"$size": "$docs"}
        }
    },
    {
        "$sort": {
            "count": -1
        }
    },
    {
        "$group": {
            "_id": None,
            "titles": {
                "$push": "$$ROOT"
            }
        }
    },
    {
        "$project": {
            "titles": 1,
            "totalRequired": {"$literal": 200},
            "titleCount": {"$size": "$titles"}
        }
    },
    {
        "$project": {
            "allocations": {
                "$map": {
                    "input": "$titles",
                    "as": "title",
                    "in": {
                        "title": "$$title.title",
                        "docs": "$$title.docs",
                        "available": "$$title.count",
                        "allocation": {
                            "$min": [
                                "$$title.count",
                                {
                                    "$ceil": {
                                        "$divide": [
                                            200,
                                            {"$size": "$titles"}
                                        ]
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    },
    {
        "$project": {
            "selected": {
                "$reduce": {
                    "input": "$allocations",
                    "initialValue": [],
                    "in": {
                        "$concatArrays": [
                            "$$value",
                            {
                                "$slice": [
                                    "$$this.docs",
                                    "$$this.allocation"
                                ]
                            }
                        ]
                    }
                }
            }
        }
    },
    {
        "$project": {
            "selected": {
                "$slice": [
                    "$selected",
                    200
                ]
            }
        }
    },
    {
        "$unwind": "$selected"
    },
    {
        "$replaceRoot": {
            "newRoot": "$selected"
        }
    }
]

print("Executing user aggregation on Target_P4_Opt...")
t0 = time.time()
selected_docs = list(target_col.aggregate(pipeline, allowDiskUse=True))
print(f"Retrieved {len(selected_docs)} documents in {time.time() - t0:.2f}s.")

# Step 1: Pre-fetch posted jobs from prod_jobiak_ai for all uniqueKeys
all_uniquekeys = [d["_id"] for d in selected_docs]
all_clientjobids = [d.get("clientJobId") for d in selected_docs if d.get("clientJobId")]

print("Checking posted status in prod_jobiak_ai.job...")
# Find all matching docs in prod_jobiak_ai.job with status == 'posted'
posted_query = {
    "$or": [
        {"clientJobId": {"$in": all_uniquekeys}, "status": "posted"},
        {"clientJobId": {"$in": all_clientjobids}, "status": "posted"},
        {"jobId": {"$in": all_clientjobids}, "status": "posted"}
    ]
}
posted_docs = list(job_col.find(posted_query, {"clientJobId": 1, "jobId": 1, "status": 1}))

posted_uniquekeys = set()
posted_clientjobids = set()
for p in posted_docs:
    if p.get("clientJobId"):
        posted_uniquekeys.add(p["clientJobId"])
        posted_clientjobids.add(p["clientJobId"])
    if p.get("jobId"):
        posted_clientjobids.add(p["jobId"])

print(f"Found {len(posted_docs)} posted matching docs in prod_jobiak_ai.")

# Step 2: Validate descriptions for location mentions
US_STATE_CODES = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'
city_state_pat = re.compile(r'\b([A-Z][a-zA-Z\s.-]+?),\s*(' + US_STATE_CODES + r')\b')
in_pat = re.compile(r'\bin\s*([A-Za-z\s]+?),\s*(' + US_STATE_CODES + r')\b', re.IGNORECASE)
false_positives = {"Rehab Management", "Management", "PT", "OT", "PTs", "OTs", "COTA", "COTAs", "SLP", "SLPs", "Therapist"}

results = []
no_loc_not_posted = []

for d in selected_docs:
    uk = d["_id"]
    cjid = d.get("clientJobId") or d.get("jobId") or ""
    title = d.get("jobtitle")
    loc = d.get("location")
    desc = d.get("jobdescription_opt") or ""
    
    # Parse text
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    
    # Check for city/state patterns like "Wayland, MA"
    detected_locations = []
    for m in city_state_pat.finditer(text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in false_positives and len(c) > 2 and not any(c.endswith(fp) for fp in ["Therapist", "Assistant"]):
            detected_locations.append(f"{c}, {s}")
            
    for m in in_pat.finditer(text):
        c, s = m.group(1).strip(), m.group(2)
        if c not in false_positives and len(c) > 2:
            detected_locations.append(f"{c}, {s}")
            
    detected_locations = list(dict.fromkeys(detected_locations))
    has_location = len(detected_locations) > 0
    
    # Also check if assigned city is in text
    assigned_city = loc.split(",")[0].strip() if loc and "," in loc else ""
    if assigned_city and len(assigned_city) > 2:
        if re.search(r'\b' + re.escape(assigned_city) + r'\b', text, re.IGNORECASE):
            has_location = True
            detected_locations.append(assigned_city)
            
    # Check posted status
    is_posted = (uk in posted_uniquekeys) or (cjid in posted_clientjobids)
    
    row = {
        "clientJobId": cjid,
        "uniqueKey": uk,
        "jobtitle": title,
        "location": loc,
        "has_location_in_description": has_location,
        "detected_locations": "; ".join(detected_locations),
        "is_posted": is_posted
    }
    results.append(row)
    
    if (not has_location) and (not is_posted):
        no_loc_not_posted.append(row)

df_all = pd.DataFrame(results)
df_all.to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\target_p4_all_evaluated.csv", index=False)

df_no_loc_not_posted = pd.DataFrame(no_loc_not_posted)
df_no_loc_not_posted.to_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\target_p4_no_location_not_posted.csv", index=False)

print(f"\n================ SUMMARY ================")
print(f"Total Selected Jobs: {len(results)}")
print(f"Jobs with location in description: {sum(1 for r in results if r['has_location_in_description'])}")
print(f"Jobs WITHOUT location in description: {sum(1 for r in results if not r['has_location_in_description'])}")
print(f"Jobs posted: {sum(1 for r in results if r['is_posted'])}")
print(f"Jobs NOT posted: {sum(1 for r in results if not r['is_posted'])}")
print(f"Jobs WITHOUT location AND NOT POSTED: {len(no_loc_not_posted)}")
print(f"=========================================\n")

if no_loc_not_posted:
    print(f"Sample clientJobIds without location & not posted ({len(no_loc_not_posted)} total):")
    for item in no_loc_not_posted[:20]:
        print(f"clientJobId: {item['clientJobId']} | uniqueKey: {item['uniqueKey']} | Title: {item['jobtitle']} | Loc: {item['location']}")
