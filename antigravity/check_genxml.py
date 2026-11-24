import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]

print("Matching creds:")
for d in creds.find({"domain": {"$regex": "xml", "$options": "i"}}):
    print(" ", d.get("domain"), "->", d.get("ip"))

cred = creds.find_one({"domain": {"$regex": "^generatexml_prod$", "$options": "i"}})
if cred:
    db_name = cred["domain"]
    client = MongoClient(cred.get("mongo_uri") or cred.get("uri"))
    db = client[db_name]
    cols = [c for c in db.list_collection_names() if c.startswith("emp-gxc-")]
    print(f"\nFound {len(cols)} 'emp-gxc-' collections in {db_name}:")
    for c in sorted(cols):
        print(" ", c)
else:
    print("Not found in mongo_creds.creds, checking root databases...")
    for dbn in mc.list_database_names():
        if "xml" in dbn.lower():
            print(" ", dbn)
