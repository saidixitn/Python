import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]
p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
p_db = p_client["prod_jobiak_ai"]
col = p_db["userAnalytics"]

# Let's count how many documents exist for this employerId
total_emp_docs = col.count_documents({"employerId": "5f16b7fba780b2085c230ea1"})
print("Total userAnalytics docs for Champion Window:", total_emp_docs, flush=True)
