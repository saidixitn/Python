import os
import time
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
client = MongoClient(creds["mongo_uri"])
coll = client["jobicarenode_prod"]["Target_P4_Opt"]

# Notice in the user's query:
# In stage 5:
# docs: {
#    $push: {
#        _id: "$uniqueKey",
#        company: "$company",
#        employerId: "$employerId",
#        jobtitle: "$jobtitle",
#        location: "$location",
#        clientJobId: "$clientJobId",
#        jobId: "$jobId",
#        jobdescription_opt: "$jobdescription_opt"
#    }
# }

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

print("Running aggregation query on Target_P4_Opt...")
t0 = time.time()
results = list(coll.aggregate(pipeline, allowDiskUse=True))
t1 = time.time()
print(f"Aggregation returned {len(results)} docs in {t1 - t0:.2f} seconds.")

if results:
    first = results[0]
    print("Sample result keys:", list(first.keys()))
    print("Sample uniqueKey (_id):", first.get("_id"))
    print("Sample clientJobId:", first.get("clientJobId"))
    print("Sample jobId:", first.get("jobId"))
    print("Sample location:", first.get("location"))
    print("Sample title:", first.get("jobtitle"))
    print("Sample desc length:", len(first.get("jobdescription_opt") or ""))
