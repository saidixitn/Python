import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))

# Find credentials
creds_col = local_client["mongo_creds"]["creds"]
all_creds = list(creds_col.find())

print("Known domains:")
for c in all_creds:
    print(c.get("domain"), c.get("db_name"))

# Let's check databases and collections for "qrm" and "target"
# Let's check prod_jobiak_ai
prod_client = MongoClient(creds_col.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])

# Check jobicarenode_prod if available
jicn_cred = creds_col.find_one({"domain": {"$regex": "jobicarenode", "$options": "i"}})
if jicn_cred:
    jicn_client = MongoClient(jicn_cred["mongo_uri"])
else:
    # check local_client or prod_client for jobicarenode_prod
    jicn_client = prod_client

print("\nSearching for emp-qrm in prod_jobiak_ai.job...")
count_qrm_prod = prod_client["prod_jobiak_ai"]["job"].count_documents({"employerId": {"$regex": "qrm", "$options": "i"}})
print("prod_jobiak_ai.job with 'qrm' in employerId:", count_qrm_prod)

# Find unique employerIds matching qrm in prod_jobiak_ai.job
qrm_emp_ids = prod_client["prod_jobiak_ai"]["job"].distinct("employerId", {"employerId": {"$regex": "qrm", "$options": "i"}})
print("Distinct employerIds with 'qrm' in prod_jobiak_ai.job:", qrm_emp_ids)

# Check all databases in prod_client
for dbname in ["jobicarenode_prod", "prod_jobiak_ai"]:
    try:
        db = prod_client[dbname]
        for colname in db.list_collection_names():
            if "target" in colname.lower() or "qrm" in colname.lower():
                print(f"Found collection: {dbname}.{colname}")
                # check count of emp-qrm
                cnt = db[colname].count_documents({"employerId": {"$regex": "qrm", "$options": "i"}})
                print(f"  Count matching 'qrm' in employerId: {cnt}")
                # check distinct employerIds
                eids = db[colname].distinct("employerId", {"employerId": {"$regex": "qrm", "$options": "i"}})
                print(f"  Distinct: {eids}")
    except Exception as e:
        print(f"Error checking {dbname}: {e}")
