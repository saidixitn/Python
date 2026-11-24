import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
mc = MongoClient(os.getenv("MONGO_URI"))
creds = mc["mongo_creds"]["creds"]

p_client = MongoClient(creds.find_one({"domain": "prod_jobiak_ai"})["mongo_uri"])
dc_client = MongoClient(creds.find_one({"domain": "directclients_prod"})["mongo_uri"])

print("prod_jobiak_ai.userAnalytics indexes:")
for idx in p_client["prod_jobiak_ai"]["userAnalytics"].list_indexes():
    print(" ", idx["name"], idx["key"])

print("\ndirectclients_prod.userAnalytics indexes:")
for idx in dc_client["directclients_prod"]["userAnalytics"].list_indexes():
    print(" ", idx["name"], idx["key"])
