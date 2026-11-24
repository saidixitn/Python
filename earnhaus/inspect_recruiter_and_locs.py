from pymongo import MongoClient
import os
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "jobicarenode_prod"})
jicn_client = MongoClient(creds["mongo_uri"])
db = jicn_client["jobicarenode_prod"]

emp_qrm = db["emp-qrm"]
target_p4 = db["Target_P4_Opt"]

# Check counts
print("emp-qrm count:", emp_qrm.count_documents({}))
print("Target_P4_Opt count for emp-jicn-qrm:", target_p4.count_documents({"employerId": "emp-jicn-qrm"}))

# Let's inspect 10 samples from each to see where recruiter info and locations appear
print("\n--- Samples from emp-qrm ---")
for doc in emp_qrm.find({}, {"description": 1, "title": 1, "city": 1, "state": 1}).limit(5):
    desc = doc.get("description", "")
    print("City:", doc.get("city"), "State:", doc.get("state"))
    # look around 'confidential', 'contact', 'recruiter', 'apply', or end of desc
    if "confidential" in desc.lower():
        idx = desc.lower().find("confidential")
        print("  Near confidential:", repr(desc[idx-50:idx+150]))
    elif "contact" in desc.lower():
        idx = desc.lower().find("contact")
        print("  Near contact:", repr(desc[idx-50:idx+150]))
    else:
        print("  Desc tail:", repr(desc[-200:]))

print("\n--- Samples from Target_P4_Opt ---")
for doc in target_p4.find({"employerId": "emp-jicn-qrm"}, {"description": 1, "jobtitle": 1, "city": 1, "state": 1}).limit(5):
    desc = doc.get("description", "")
    print("City:", doc.get("city"), "State:", doc.get("state"))
    if "confidential" in desc.lower():
        idx = desc.lower().find("confidential")
        print("  Near confidential:", repr(desc[idx-50:idx+150]))
    elif "contact" in desc.lower():
        idx = desc.lower().find("contact")
        print("  Near contact:", repr(desc[idx-50:idx+150]))
    else:
        print("  Desc tail:", repr(desc[-200:]))
