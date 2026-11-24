import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# Jobicarenode
jic_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jic_client = MongoClient(jic_creds["mongo_uri"])
coll = jic_client["jobicarenode_prod"]["Target_P4_Opt"]

# Prod jobiak
prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

# Also let's check ETL_Scraping_Data
etl_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "ETL_Scrapping_Data"})
etl_col = None
if etl_creds:
    etl_client = MongoClient(etl_creds["mongo_uri"])
    etl_col = etl_client["ETL_Scrapping_Data"]["ETL_Scraping_Data"]

sys.path.append(r"c:\Users\JOBIAK\Documents\Python\earnhaus")
from run_user_query import pipeline

results = list(coll.aggregate(pipeline, allowDiskUse=True))
print(f"Got {len(results)} sampled docs from aggregation.")

for s in results[:5]:
    uniquekey = s["_id"]
    client_job_id = s.get("clientJobId")
    job_id = s.get("jobId")
    print(f"\nTarget_P4 doc: uniqueKey={uniquekey} | clientJobId={client_job_id}")
    
    # Check in prod_jobiak_ai.job by clientJobId (which stores uniqueKey in prod_jobiak_ai)
    match_by_uniquekey = job_col.find_one({"clientJobId": uniquekey})
    print(f"  Match in prod_jobiak_ai by uniqueKey: status={match_by_uniquekey.get('status') if match_by_uniquekey else None}")
    
    # Check in prod_jobiak_ai.job by client_job_id (Job-XXXXXX)
    match_by_jobid = job_col.find_one({"$or": [{"clientJobId": client_job_id}, {"jobId": client_job_id}]})
    print(f"  Match in prod_jobiak_ai by client_job_id: {match_by_jobid.get('jobId') if match_by_jobid else None}")
    
    if etl_col:
        etl_match = etl_col.find_one({"clientJobId": client_job_id})
        print(f"  Match in ETL_Scraping_Data by client_job_id: {bool(etl_match)}")
