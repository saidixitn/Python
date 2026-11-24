"""
Antigravity Central Database & Client Helper
============================================
Provides thread-safe dynamic connection resolution across all multi-tenant databases:
- Proxy (prod_jobiak_ai, ETL_Scrapping_Data, data_cleansing, proxy_stats)
- Direct Apply / Subdomain (directclients_prod)
- Programmatic ({client}_prod)
- Central Registries (daily_stats, mongo_creds)
"""

import os
import threading
import logging
from dotenv import load_dotenv
from pymongo import MongoClient

logger = logging.getLogger("antigravity.db_helper")

# Load environment
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

_CLIENT_CACHE = {}
_DB_CACHE = {}
_CACHE_LOCK = threading.Lock()


def get_root_client() -> MongoClient:
    """Returns the primary MongoClient connected via MONGO_URI."""
    if not MONGO_URI:
        raise ValueError("MONGO_URI not found in environment (.env)")
    with _CACHE_LOCK:
        if "ROOT" not in _CLIENT_CACHE:
            _CLIENT_CACHE["ROOT"] = MongoClient(MONGO_URI, maxPoolSize=100)
        return _CLIENT_CACHE["ROOT"]


def get_database_by_name(db_name: str):
    """
    Dynamically resolves a database name by looking up its connection string in
    mongo_creds.creds on the root MongoDB instance. Caches clients and db handles.
    """
    with _CACHE_LOCK:
        if db_name in _DB_CACHE:
            return _DB_CACHE[db_name]

    root = get_root_client()
    creds_col = root["mongo_creds"]["creds"]
    doc = creds_col.find_one({"domain": db_name})

    if not doc:
        # Fallback check on root client directly
        logger.warning(f"No credentials record found in mongo_creds.creds for '{db_name}'. Checking root cluster.")
        db = root[db_name]
    else:
        uri = doc.get("mongo_uri") or doc.get("uri")
        if not uri:
            raise ValueError(f"Credentials document for '{db_name}' contains no 'mongo_uri' or 'uri' field.")
        client = MongoClient(uri, maxPoolSize=100)
        db = client[db_name]
        with _CACHE_LOCK:
            _CLIENT_CACHE[db_name] = client

    with _CACHE_LOCK:
        _DB_CACHE[db_name] = db
    return db


def get_collections_for_domain(domain_type: str, db):
    """
    Standard collection resolver based on domain architecture:
    - 'Proxy' -> job, userAnalytics, jobsGoogleSubmittedLog
    - 'Direct' / 'Programmatic' -> Target_P4_Opt, userAnalytics, aj_jp_google_logs, aj_jp_jobqueue
    """
    if domain_type == "Proxy":
        return {
            "jobs": db["job"],
            "analytics": db["userAnalytics"],
            "proxy_logs": db["jobsGoogleSubmittedLog"]
        }
    else:
        return {
            "jobs": db["Target_P4_Opt"],
            "analytics": db["userAnalytics"],
            "logs": db["aj_jp_google_logs"],
            "queue": db["aj_jp_jobqueue"]
        }
