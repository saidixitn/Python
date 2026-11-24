import os
import gspread
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
gc = gspread.service_account(filename="credentials.json")
sh = gc.open_by_key("1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds")
ws = sh.worksheet("Domains")
rows = ws.get_all_values()
print(f"Total rows in Domains sheet: {len(rows)}")
for r in rows:
    print(" ", r)

mc = MongoClient(os.getenv("MONGO_URI"))
print("\nExisting databases on root cluster:", mc.list_database_names())
creds_col = mc["mongo_creds"]["creds"]
dc_prod_cred = creds_col.find_one({"domain": "dc_prod"})
print("dc_prod in mongo_creds.creds:", dc_prod_cred)
