"""
generateXml_prod: Title-Wise Feed Comparison Across All 'emp-gxc-*' Collections
==============================================================================
Target Companies: Albertsons, Gopuff, Doordash, Uber, Grubhub
Workers: 20 concurrent threads across all 396 'emp-gxc-*' collections
Projected Fields: company, title, cpa, cpc (+ source collection/feed name)
Outputs:
  1. emp_gxc_title_wise_feed_comparison.csv (Title-wise comparison across feeds)
  2. emp_gxc_company_feed_summary.csv (Company + Feed level summary)
"""

import os
import re
import csv
import time
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("GenXmlFeedCompare")

TARGET_REGEX = re.compile(r"(albertsons|gopuff|doordash|uber|grubhub)", re.IGNORECASE)


def normalize_company(raw_comp: str) -> str:
    low = (raw_comp or "").lower()
    if "albertsons" in low:
        return "Albertsons"
    if "gopuff" in low:
        return "Gopuff"
    if "doordash" in low:
        return "DoorDash"
    if "grubhub" in low:
        return "Grubhub"
    if "ubereats" in low or "uber eats" in low:
        return "Uber Eats"
    if "uber" in low:
        return "Uber"
    return raw_comp


def safe_float(val):
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace("$", "").strip())
    except (ValueError, TypeError):
        return None


def scan_collection(db, col_name: str):
    """Queries a single emp-gxc-* collection for target companies."""
    if col_name.startswith(".") or col_name.endswith("."):
        return col_name, {}

    query = {"company": {"$regex": TARGET_REGEX}}
    projection = {"_id": 0, "company": 1, "title": 1, "cpa": 1, "cpc": 1}

    agg = defaultdict(lambda: {"count": 0, "cpas": [], "cpcs": [], "raw_companies": set()})
    try:
        col = db.get_collection(col_name)
        for doc in col.find(query, projection).batch_size(5000):
            raw_comp = str(doc.get("company") or "").strip()
            comp_norm = normalize_company(raw_comp)
            title = str(doc.get("title") or "").strip()
            cpa_val = doc.get("cpa")
            cpc_val = doc.get("cpc")

            key = (comp_norm, title)
            agg[key]["count"] += 1
            agg[key]["raw_companies"].add(raw_comp)
            if cpa_val is not None and str(cpa_val).strip() != "":
                agg[key]["cpas"].append(str(cpa_val).strip())
            if cpc_val is not None and str(cpc_val).strip() != "":
                agg[key]["cpcs"].append(str(cpc_val).strip())
        return col_name, agg
    except Exception as e:
        logger.error(f"Error scanning {col_name}: {e}")
        return col_name, {}


def main():
    t0 = time.time()
    load_dotenv()
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in .env")

    root_client = MongoClient(mongo_uri)
    cred = root_client["mongo_creds"]["creds"].find_one({"domain": "generateXml_prod"})
    if not cred:
        raise ValueError("generateXml_prod credentials not found in mongo_creds.creds")

    gen_client = MongoClient(
        cred.get("mongo_uri") or cred.get("uri"),
        maxPoolSize=50,
        socketTimeoutMS=180000,
        connectTimeoutMS=30000,
        retryReads=True
    )
    db = gen_client["generateXml_prod"]

    collections = sorted([c for c in db.list_collection_names() if c.startswith("emp-gxc-")])
    logger.info(f"Found {len(collections)} 'emp-gxc-' collections in generateXml_prod. Launching 20 workers...")

    all_results = []  # (col_name, agg_dict)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(scan_collection, db, c) for c in collections]
        for fut in as_completed(futures):
            col_name, agg = fut.result()
            if agg:
                all_results.append((col_name, agg))
                logger.info(f"  Match in {col_name}: {len(agg)} (company, title) groups, {sum(v['count'] for v in agg.values())} docs")

    # Build Title-Wise Feed Comparison rows
    # Group by (Company, Title) -> list of feeds + metrics, and also flat feed-level rows
    flat_rows = []
    title_feeds_map = defaultdict(list)

    for col_name, agg in sorted(all_results, key=lambda x: x[0]):
        for (comp_norm, title), data in agg.items():
            distinct_cpas = sorted(set(data["cpas"]))
            distinct_cpcs = sorted(set(data["cpcs"]))
            num_cpas = [x for x in (safe_float(v) for v in data["cpas"]) if x is not None]
            num_cpcs = [x for x in (safe_float(v) for v in data["cpcs"]) if x is not None]

            avg_cpa = round(sum(num_cpas) / len(num_cpas), 2) if num_cpas else ""
            avg_cpc = round(sum(num_cpcs) / len(num_cpcs), 2) if num_cpcs else ""

            row = {
                "Company (Normalized)": comp_norm,
                "Raw Company Names": " | ".join(sorted(data["raw_companies"])),
                "Title": title,
                "Collection (Feed)": col_name,
                "Job Count": data["count"],
                "Distinct CPA Values": " | ".join(distinct_cpas[:10]),
                "Distinct CPC Values": " | ".join(distinct_cpcs[:10]),
                "Avg CPA": avg_cpa,
                "Avg CPC": avg_cpc,
            }
            flat_rows.append(row)
            title_feeds_map[(comp_norm, title)].append(
                f"{col_name} (Jobs:{data['count']}, CPA:{','.join(distinct_cpas[:3]) or 'N/A'}, CPC:{','.join(distinct_cpcs[:3]) or 'N/A'})"
            )

    # Sort flat comparison cleanly by Company, Title, Job Count desc
    flat_rows.sort(key=lambda r: (r["Company (Normalized)"], r["Title"].lower(), -r["Job Count"]))

    # Also build cross-feed summary per (Company, Title)
    pivot_rows = []
    for (comp_norm, title), feed_strs in sorted(title_feeds_map.items(), key=lambda x: (x[0][0], x[0][1].lower())):
        total_jobs = sum(
            r["Job Count"] for r in flat_rows
            if r["Company (Normalized)"] == comp_norm and r["Title"] == title
        )
        pivot_rows.append({
            "Company": comp_norm,
            "Title": title,
            "Feed Count": len(feed_strs),
            "Total Jobs Across Feeds": total_jobs,
            "Feeds Comparison (Collection | Jobs | CPA | CPC)": " ; ".join(feed_strs)
        })

    # Export CSV 1: Detailed Title-Wise Feed Comparison
    csv1_path = r"C:\Users\JOBIAK\Documents\Python\emp_gxc_title_wise_feed_comparison.csv"
    with open(csv1_path, "w", newline="", encoding="utf-8") as f:
        if flat_rows:
            writer = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
            writer.writeheader()
            writer.writerows(flat_rows)

    # Export CSV 2: Cross-Feed Summary per Title
    csv2_path = r"C:\Users\JOBIAK\Documents\Python\emp_gxc_title_cross_feed_summary.csv"
    with open(csv2_path, "w", newline="", encoding="utf-8") as f:
        if pivot_rows:
            writer = csv.DictWriter(f, fieldnames=list(pivot_rows[0].keys()))
            writer.writeheader()
            writer.writerows(pivot_rows)

    # Copy to Downloads & Artifacts
    for d in [r"C:\Users\JOBIAK\Downloads", r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"]:
        os.makedirs(d, exist_ok=True)
        for src in [csv1_path, csv2_path]:
            dst = os.path.join(d, os.path.basename(src))
            try:
                with open(src, "rb") as sf, open(dst, "wb") as df:
                    df.write(sf.read())
            except Exception:
                pass

    print("\n" + "=" * 75)
    print(f"COMPLETED IN {time.time() - t0:.2f}s (Scanned {len(collections)} collections with 20 workers)")
    print(f"  Collections with matches: {len(all_results)}")
    print(f"  Detailed Feed Comparison CSV: {csv1_path} ({len(flat_rows)} rows)")
    print(f"  Cross-Feed Title Summary CSV: {csv2_path} ({len(pivot_rows)} rows)")
    print("=" * 75)


if __name__ == "__main__":
    main()
