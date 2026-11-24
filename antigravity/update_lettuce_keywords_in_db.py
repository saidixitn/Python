import os
import re
import logging
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

def update_lettuce_keywords():
    """
    Finds all Lettuce jobs (employerId: 'emp-jbk-lettuce', gpost: 5)
    in directclients_prod.Target_P4_Opt that contain {city} or {state}
    placeholders in locationKeywords, replaces them with actual city/state values,
    and updates MongoDB in bulk.
    """
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in .env")

    primary_client = MongoClient(mongo_uri)
    creds_col = primary_client["mongo_creds"]["creds"]
    cred_doc = creds_col.find_one({"domain": "directclients_prod"})
    if not cred_doc:
        raise ValueError("Credentials for 'directclients_prod' not found")

    dc_uri = cred_doc.get("mongo_uri") or cred_doc.get("uri")
    dc_client = MongoClient(dc_uri)
    col = dc_client["directclients_prod"]["Target_P4_Opt"]

    query = {
        "employerId": "emp-jbk-lettuce",
        "gpost": 5
    }
    projection = {
        "_id": 1,
        "jobtitle": 1,
        "location": 1,
        "locationKeywords": 1
    }

    logger.info("Fetching Lettuce jobs...")
    cursor = col.find(query, projection)

    bulk_ops = []
    for doc in cursor:
        kws = doc.get("locationKeywords")
        if not kws or not isinstance(kws, list):
            continue

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

        cleaned_kws = []
        for kw in kws:
            if isinstance(kw, str):
                cleaned_kw = re.sub(r"\{city\}", city, kw, flags=re.IGNORECASE)
                cleaned_kw = re.sub(r"\{state\}", state, cleaned_kw, flags=re.IGNORECASE)
                cleaned_kws.append(cleaned_kw)
            else:
                cleaned_kws.append(kw)

        bulk_ops.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$set": {"locationKeywords": cleaned_kws}}
            )
        )

    logger.info(f"Prepared {len(bulk_ops)} updates.")
    if bulk_ops:
        res = col.bulk_write(bulk_ops, ordered=False)
        logger.info(f"Bulk update complete! Matched: {res.matched_count}, Modified: {res.modified_count}")
    else:
        logger.info("No documents required update.")

if __name__ == "__main__":
    # Uncomment the function call below to execute the DB update:
    # update_lettuce_keywords()
    print("Script ready. Call update_lettuce_keywords() to write changes directly to MongoDB.")
