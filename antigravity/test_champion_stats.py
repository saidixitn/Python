import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
oldstats = mc["daily_stats"]["oldstats"]
output = mc["daily_stats"]["output"]

emp = "5f16b7fba780b2085c230ea1"
print("Oldstats docs count for Champion:", oldstats.count_documents({"employerId": emp}))
for doc in oldstats.find({"employerId": emp}).sort("Date", 1).limit(5):
    print("  oldstats:", doc.get("Date"), "DB_Clicks:", doc.get("DB_Clicks"))

for doc in oldstats.find({"employerId": emp}).sort("Date", -1).limit(5):
    print("  oldstats latest:", doc.get("Date"), "DB_Clicks:", doc.get("DB_Clicks"))

print("Output docs count for Champion:", output.count_documents({"employerId": emp}))
for doc in output.find({"employerId": emp}).sort("Date", 1).limit(5):
    print("  output:", doc.get("Date"), "DB_Clicks:", doc.get("DB_Clicks"))
