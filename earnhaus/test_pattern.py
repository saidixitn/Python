import os
import re
import pandas as pd
from pymongo import MongoClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv(r"./.env")
local_client = MongoClient(os.getenv("MONGO_URI"))
creds = local_client["mongo_creds"]["creds"].find_one({"domain": "prod_jobiak_ai"})
prod_client = MongoClient(creds["mongo_uri"])
job_col = prod_client["prod_jobiak_ai"]["job"]

df = pd.read_csv(r"C:/Users/JOBIAK/.gemini/antigravity/brain/6e0488a6-8f1e-4ae7-9214-e018b0901935/.user_uploaded/media_1793970059780_660dbf16.csv")
all_ids = df["jobId"].tolist()

docs = list(job_col.find({"jobId": {"$in": all_ids}}, {"jobId": 1, "description": 1, "location": 1}))

wayland_ma_exact = []
wayland_any = []
city_st_matches = {}

for d in docs:
    desc = d.get("description", "")
    if "wayland, ma" in desc.lower() or "wayland,ma" in desc.lower() or "wayland ma" in desc.lower():
        wayland_ma_exact.append(d["jobId"])
    if "wayland" in desc.lower():
        wayland_any.append(d["jobId"])
    # find [A-Z][a-z]+,\s*[A-Z]{2}
    soup = BeautifulSoup(desc, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    m = re.findall(r'([A-Z][a-zA-Z\s]{2,15},\s*[A-Z]{2})', text)
    for match in m:
        city_st_matches[match] = city_st_matches.get(match, 0) + 1

print(f"Wayland exact (Wayland, MA): {len(wayland_ma_exact)}")
print(f"Wayland any: {len(wayland_any)}")
print(f"Top 20 City, ST matches in all descriptions:")
for k, v in sorted(city_st_matches.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"  {k}: {v}")
