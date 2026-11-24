import os
import re
import csv
import logging
from dotenv import load_dotenv
from pymongo import MongoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in .env")

    logger.info("Connecting to primary MongoDB...")
    primary_client = MongoClient(mongo_uri)
    creds_col = primary_client["mongo_creds"]["creds"]
    
    cred_doc = creds_col.find_one({"domain": "directclients_prod"})
    if not cred_doc:
        raise ValueError("Credentials for 'directclients_prod' not found in mongo_creds.creds")
    
    dc_uri = cred_doc.get("mongo_uri") or cred_doc.get("uri")
    logger.info("Connecting to directclients_prod...")
    dc_client = MongoClient(dc_uri)
    col = dc_client["directclients_prod"]["Target_P4_Opt"]

    query = {
        "employerId": "emp-jbk-lettuce",
        "gpost": 5
    }
    projection = {
        "employerId": 1,
        "jobtitle": 1,
        "location": 1,
        "locationKeywords": 1,
        "submittedUrl": 1
    }

    logger.info("Querying Lettuce jobs with gpost: 5...")
    cursor = col.find(query, projection)

    records = []
    max_keywords = 0

    for doc in cursor:
        kws = doc.get("locationKeywords")
        if not kws or not isinstance(kws, list):
            continue

        # Check if placeholders exist in locationKeywords
        has_placeholder = any(
            isinstance(kw, str) and ("{city}" in kw.lower() or "{state}" in kw.lower())
            for kw in kws
        )
        if not has_placeholder:
            continue

        loc_str = doc.get("location", "")
        parts = [p.strip() for p in loc_str.split(",")]
        city = parts[0] if len(parts) > 0 else ""
        state = parts[1] if len(parts) > 1 else ""

        # Replace placeholders
        cleaned_kws = []
        for kw in kws:
            if isinstance(kw, str):
                cleaned_kw = re.sub(r"\{city\}", city, kw, flags=re.IGNORECASE)
                cleaned_kw = re.sub(r"\{state\}", state, cleaned_kw, flags=re.IGNORECASE)
                cleaned_kws.append(cleaned_kw)
            else:
                cleaned_kws.append(kw)

        if len(cleaned_kws) > max_keywords:
            max_keywords = len(cleaned_kws)

        records.append({
            "_id": str(doc.get("_id")),
            "jobtitle": doc.get("jobtitle", ""),
            "location": loc_str,
            "submittedUrl": doc.get("submittedUrl", ""),
            "cleaned_keywords": cleaned_kws
        })

    logger.info(f"Found {len(records)} jobs needing keywords update. Max keywords: {max_keywords}")

    # Build fieldnames
    headers = ["jobtitle", "location", "submittedUrl"]
    for i in range(1, max_keywords + 1):
        headers.append(f"keyword_{i}")

    # File paths
    output_paths = [
        r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\Lettuce_Visibility_Keywords_Updated.csv",
        r"C:\Users\JOBIAK\Documents\Python\Lettuce_Visibility_Keywords_Updated.csv",
        r"C:\Users\JOBIAK\Downloads\Lettuce_Visibility_Keywords_Updated.csv"
    ]

    for out_path in output_paths:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in records:
                row = [r["jobtitle"], r["location"], r["submittedUrl"]]
                kws = r["cleaned_keywords"]
                for i in range(max_keywords):
                    row.append(kws[i] if i < len(kws) else "")
                writer.writerow(row)
        logger.info(f"Successfully saved {len(records)} rows to {out_path}")

if __name__ == "__main__":
    main()
