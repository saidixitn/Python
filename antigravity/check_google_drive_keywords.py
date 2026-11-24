import os
import sys
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from pymongo import MongoClient
from urllib.parse import quote_plus, urlparse, urlunparse
from dotenv import load_dotenv

load_dotenv(r"./.env")

def safe_encode_uri(uri):
    p = urlparse(uri)
    if p.username or p.password:
        auth = quote_plus(p.username or "")
        if p.password:
            auth += f":{quote_plus(p.password)}"
        netloc = f"{auth}@{p.hostname}" + (f":{p.port}" if p.port else "")
        return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
    return uri

central = MongoClient(safe_encode_uri(os.getenv("MONGO_URI")))
doc = central["google_creds"]["creds"].find_one({"name": "google_credentials"}) or central["google_creds"]["creds"].find_one({}, {"content": 1})
creds = Credentials.from_service_account_info(
    doc["content"],
    scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]
)

try:
    drive_service = build("drive", "v3", credentials=creds)
    results = drive_service.files().list(
        q="name contains 'Keywords' or name contains 'Yes'",
        fields="files(id, name, mimeType, webViewLink)",
        pageSize=30
    ).execute()
    items = results.get("files", [])
    print(f"Drive search results ({len(items)} found):")
    for item in items:
        print(f"  {item['name']} | ID: {item['id']} | Type: {item['mimeType']}")
except Exception as e:
    print("Error querying Google Drive:", e)
