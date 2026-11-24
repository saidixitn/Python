import os
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import Counter

load_dotenv()
primary_client = MongoClient(os.getenv("MONGO_URI"))
creds = primary_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
db = prod_client["prod_jobiak_ai"]

emp_id = "6a904f26060e8f0b78b0dc81"
analytics = db["userAnalytics"]

# Check distinct crawlers / userAgents for isBot: True
bot_crawlers = analytics.aggregate([
    {"$match": {"employerId": emp_id, "isBot": True}},
    {"$group": {"_id": "$crawler", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 10}
])
print("Top Bot Crawlers for isBot: True:")
for b in bot_crawlers:
    print(f"  {b['_id']}: {b['count']}")

# Check if Googlebot appears specifically
googlebot_count = analytics.count_documents({
    "employerId": emp_id,
    "isBot": True,
    "userAgent": {"$regex": "Googlebot", "$options": "i"}
})
print(f"Total Googlebot userAgent records: {googlebot_count}")

# Check country distribution for isBot: True
countries = analytics.aggregate([
    {"$match": {"employerId": emp_id, "isBot": True}},
    {"$group": {"_id": "$country", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}},
    {"$limit": 5}
])
print("Top Countries for isBot: True:")
for c in countries:
    print(f"  {c['_id']}: {c['count']}")
