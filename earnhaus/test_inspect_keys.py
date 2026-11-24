import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

prod_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(prod_creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

dc_creds = local_client["mongo_creds"]["creds"].find_one({"domain": "data_cleansing"})
dc_client = MongoClient(dc_creds["mongo_uri"])
etl_col = dc_client["data_cleansing"]["ETL_Job_Log"]

# Sample job from Target_P4_Opt:
# uniqueKey: cook~~council`grove~~ks~~us~~group`healthcare`inc`services
# clientJobId: 726418

print("Testing search in prod_jobiak_ai:")
test_uk = "cook~~council`grove~~ks~~us~~group`healthcare`inc`services"
m1 = job_col.find_one({"employerId": "6a904f26060e8f0b78b0dc81", "clientJobId": test_uk})
print("Match by uniqueKey in prod_jobiak_ai:", bool(m1))
m2 = job_col.find_one({"employerId": "6a904f26060e8f0b78b0dc81", "clientJobId": "726418"})
print("Match by int/str clientJobId in prod_jobiak_ai:", bool(m2))
m3 = job_col.find_one({"employerId": "6a904f26060e8f0b78b0dc81", "clientJobId": 726418})
print("Match by int clientJobId in prod_jobiak_ai:", bool(m3))

print("\nTesting search in ETL_Job_Log:")
e1 = etl_col.find_one({"employerId": "6a904f26060e8f0b78b0dc81", "data.clientJobId": test_uk})
print("Match by uniqueKey in ETL_Job_Log:", bool(e1))
e2 = etl_col.find_one({"employerId": "6a904f26060e8f0b78b0dc81", "data.clientJobId": "726418"})
print("Match by int/str clientJobId in ETL_Job_Log:", bool(e2))
e3 = etl_col.find_one({"employerId": "6a904f26060e8f0b78b0dc81", "data.clientJobId": 726418})
print("Match by int clientJobId in ETL_Job_Log:", bool(e3))

# Let's inspect some clientJobId values in ETL_Job_Log for 6a904f26060e8f0b78b0dc81
sample_etls = list(etl_col.find({"employerId": "6a904f26060e8f0b78b0dc81"}, {"data.clientJobId": 1}).limit(5))
print("Sample data.clientJobId in ETL_Job_Log:")
for s in sample_etls:
    print(" ", s.get("data", {}).get("clientJobId"))

# Let's inspect some clientJobId values in prod_jobiak_ai for 6a904f26060e8f0b78b0dc81
sample_prods = list(job_col.find({"employerId": "6a904f26060e8f0b78b0dc81"}, {"clientJobId": 1, "title": 1}).limit(5))
print("Sample clientJobId in prod_jobiak_ai:")
for s in sample_prods:
    print(" ", s.get("clientJobId"), "| Title:", s.get("title"))
