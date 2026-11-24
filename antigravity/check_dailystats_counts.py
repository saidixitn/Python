import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
oldstats = mc["daily_stats"]["oldstats"]
output = mc["daily_stats"]["output"]

domains = [
    ("qrmhealth.com/gfj/", "Proxy", "6a7b516d060e8f0b78b0dc5a"),
    ("championwindow.com/gfj/", "Proxy", "5f16b7fba780b2085c230ea1"),
    ("imperialsupplies.com/jobiak", "Proxy", "5e6f1017a780b23e130a1c3b"),
    ("gfj.cooperfarms.com/", "Direct Apply", "emp-jbk-cooperfarms"),
    ("gfj.virtahealth.com/", "Direct Apply", "emp-jbk-virtahealth"),
    ("gfj.lettuce.com", "Direct Apply", "emp-jbk-lettuce"),
    ("yescommunities.com/gfj/", "Proxy", "6a86c3d7060e8f0b78b0dc66"),
    ("concentrix.com/gfj/", "Proxy", "6a8871d1060e8f0b78b0dc69"),
    ("hcsgcorp.com/gfj/", "Proxy", "6a904f26060e8f0b78b0dc81"),
    ("abskids.com/gfj/", "Proxy", "6aa8d214060e8f0b78b0dc87"),
    ("suncrestcare.com/gfj/", "Proxy", "6ad8dd02060e8f0b78b0dc9a"),
]

print("Checking daily_stats for domains:")
for dom, dtype, emp in domains:
    c_old = oldstats.count_documents({"employerId": emp})
    c_out = output.count_documents({"employerId": emp})
    print(f"{emp} ({dom}): oldstats={c_old}, output={c_out}")
