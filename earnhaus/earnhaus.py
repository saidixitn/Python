"""
EarnHaus Job & Analytics Extractor
==================================

Requirements:
1. Employer ID: 68b8133b060e8f5df1a6c3a7 (EarnHaus).
2. Filter jobs posted in the last 2 days.
3. Select 5 unique titles and 5 unique locations.
4. Match locations against `old_locations.old_set` where Population is between 20k and 30k (or configurable).
   - In `old_set`, Location format: "Affton, MO, US, 63123" / "Affton, MO, US".
   - In `job`, Location format: "Affton,MO,US".
5. For each of the 5 jobs:
   - Perform lookup in `prod_jobiak_ai.userAnalytics` matching `job.jobId` -> `userAnalytics.childJobId` (or `jobId`).
   - Count user agents matching "Googlebot" and "Firebase" (Google-Firebase).
   - Provide the job's live/submitted URL.
6. Export results to CSV.
"""

import os
import sys
import csv
import argparse
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Defaults
DEFAULT_EMPLOYER_ID = "68b8133b060e8f5df1a6c3a7"
DEFAULT_POP_MIN = 20000
DEFAULT_POP_MAX = 30000
DEFAULT_DAYS = 2
DEFAULT_COUNT = 5
DEFAULT_CSV_PATH = os.path.join(os.path.dirname(__file__), "earnhaus_jobs.csv")


def get_mongo_client():
    """Return local MongoClient using MONGO_URI."""
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise ValueError("MONGO_URI not found in environment variables (.env)")
    return MongoClient(uri)


def get_remote_db(local_client, db_name="prod_jobiak_ai"):
    """Fetch credentials from mongo_creds.creds and return target database handle."""
    creds = local_client["mongo_creds"]["creds"].find_one(
        {"domain": db_name}, {"_id": 0, "mongo_uri": 1}
    )
    if not creds or "mongo_uri" not in creds:
        raise ValueError(f"No mongo_uri found in mongo_creds.creds for: {db_name}")
    client = MongoClient(creds["mongo_uri"])
    return client[db_name]


def normalize_location_str(loc_str: str) -> str:
    """
    Normalize location string to 'CITY,STATE,COUNTRY' (uppercase, stripped, no spaces).
    Handles:
      - 'Affton, MO, US, 63123' -> 'AFFTON,MO,US'
      - 'Affton,MO,US'          -> 'AFFTON,MO,US'
      - 'Affton, MO, US'        -> 'AFFTON,MO,US'
    """
    if not loc_str:
        return ""
    parts = [p.strip().upper() for p in str(loc_str).split(",") if p.strip()]
    if len(parts) >= 3:
        return f"{parts[0]},{parts[1]},{parts[2]}"
    return "".join(parts)


def load_population_map(local_client, pop_min: int, pop_max: int) -> dict:
    """
    Query old_locations.old_set for locations within [pop_min, pop_max].
    Returns a lookup dictionary mapping normalized location keys to metadata.
    """
    old_set = local_client["old_locations"]["old_set"]
    query = {
        "$and": [
            {"Population": {"$gte": pop_min}},
            {"Population": {"$lte": pop_max}}
        ]
    }
    projection = {
        "Location": 1,
        "City, State, Country": 1,
        "City": 1,
        "State": 1,
        "Country": 1,
        "Population": 1,
        "Zipcode": 1
    }

    print(f"[*] Querying old_locations.old_set for population between {pop_min:,} and {pop_max:,}...")
    cursor = old_set.find(query, projection)
    
    loc_map = {}
    for doc in cursor:
        if doc.get("City, State, Country"):
            k1 = normalize_location_str(doc["City, State, Country"])
            if k1:
                loc_map[k1] = doc
        
        if doc.get("Location"):
            k2 = normalize_location_str(doc["Location"])
            if k2:
                loc_map[k2] = doc

    print(f"[+] Loaded {len(loc_map):,} unique location keys from old_set.")
    return loc_map


def fetch_candidate_jobs(prod_db, employer_id: str, days: int, loc_map: dict, target_count: int = 5):
    """
    Retrieve jobs posted in the last `days` from prod_jobiak_ai.job.
    Filters for unique titles, unique locations, and matching population in `loc_map`.
    """
    job_col = prod_db["job"]

    latest_job = job_col.find_one({"employerId": employer_id}, sort=[("datePosted", -1)])
    if latest_job and latest_job.get("datePosted"):
        reference_time = latest_job["datePosted"]
    else:
        reference_time = datetime.now(timezone.utc)

    cutoff_date = reference_time - timedelta(days=days)
    print(f"[*] Reference date: {reference_time} (UTC)")
    print(f"[*] Searching jobs posted since {cutoff_date} (last {days} days)...")

    query = {
        "employerId": employer_id,
        "datePosted": {"$gte": cutoff_date}
    }
    projection = {
        "jobId": 1,
        "title": 1,
        "location": 1,
        "submittedUrl": 1,
        "url": 1,
        "datePosted": 1,
        "status": 1
    }

    cursor = job_col.find(query, projection).sort("datePosted", -1)

    matched_jobs = []
    seen_titles = set()
    seen_locations = set()

    for job in cursor:
        raw_loc = job.get("location", "")
        norm_loc = normalize_location_str(raw_loc)
        raw_title = (job.get("title") or "").strip()
        norm_title = raw_title.lower()

        if not norm_loc or not norm_title:
            continue

        if norm_loc in loc_map:
            if norm_title not in seen_titles and norm_loc not in seen_locations:
                seen_titles.add(norm_title)
                seen_locations.add(norm_loc)
                
                pop_info = loc_map[norm_loc]
                matched_jobs.append({
                    "jobId": str(job.get("jobId")),
                    "title": raw_title,
                    "location": raw_loc,
                    "datePosted": job.get("datePosted"),
                    "submittedUrl": job.get("submittedUrl") or job.get("url"),
                    "population": pop_info.get("Population"),
                    "matched_location_str": pop_info.get("Location"),
                    "matched_city_st_co": pop_info.get("City, State, Country")
                })

                if len(matched_jobs) >= target_count:
                    break

    print(f"[+] Found {len(matched_jobs)} matching jobs meeting all criteria.")
    return matched_jobs


def get_user_agent_analytics(prod_db, employer_id: str, job_id: str) -> dict:
    """
    Look up userAnalytics for a specific jobId / childJobId.
    Counts Googlebot and Firebase user agents.
    """
    ua_col = prod_db["userAnalytics"]
    query = {
        "employerId": employer_id,
        "$or": [
            {"childJobId": job_id},
            {"jobId": job_id}
        ]
    }
    
    docs = list(ua_col.find(query, {"userAgent": 1, "isBot": 1, "createdDt": 1}))
    
    googlebot_count = 0
    firebase_count = 0
    other_bot_count = 0
    human_count = 0
    user_agents_seen = set()

    for d in docs:
        ua_str = str(d.get("userAgent", "")).strip()
        if ua_str:
            user_agents_seen.add(ua_str)
        ua_lower = ua_str.lower()
        
        is_fb = "firebase" in ua_lower
        is_gb = "googlebot" in ua_lower or ("google" in ua_lower and "bot" in ua_lower and not is_fb)
        
        if is_fb:
            firebase_count += 1
        if is_gb:
            googlebot_count += 1
        
        if not is_fb and not is_gb:
            if d.get("isBot"):
                other_bot_count += 1
            else:
                human_count += 1

    return {
        "total_hits": len(docs),
        "googlebot_count": googlebot_count,
        "firebase_count": firebase_count,
        "other_bot_count": other_bot_count,
        "human_count": human_count,
        "distinct_user_agents": list(user_agents_seen)
    }


def export_to_csv(results: list, csv_path: str):
    """Write results to a CSV file."""
    fieldnames = [
        "Job ID",
        "Title",
        "Date Posted",
        "Location",
        "Old Set Location",
        "Population",
        "Submitted URL",
        "User Agent"
    ]
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            ua_str = "; ".join(r["user_agents"]) if r["user_agents"] else "None recorded"
            dt_str = r["datePosted"].strftime("%Y-%m-%d %H:%M:%S UTC") if isinstance(r["datePosted"], datetime) else str(r["datePosted"])
            writer.writerow({
                "Job ID": r["jobId"],
                "Title": r["title"],
                "Date Posted": dt_str,
                "Location": r["location"],
                "Old Set Location": r["matched_location_str"],
                "Population": r["population"],
                "Submitted URL": r["submittedUrl"],
                "User Agent": ua_str
            })
    print(f"[+] Successfully exported {len(results)} records to: {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="EarnHaus Job & Analytics Extractor")
    parser.add_argument("--employer-id", default=DEFAULT_EMPLOYER_ID, help="EarnHaus Employer ID")
    parser.add_argument("--pop-min", type=int, default=DEFAULT_POP_MIN, help="Minimum population (default: 20000)")
    parser.add_argument("--pop-max", type=int, default=DEFAULT_POP_MAX, help="Maximum population (default: 30000)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Date window in days (default: 2)")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of unique jobs to extract (default: 5)")
    parser.add_argument("--csv-file", default=DEFAULT_CSV_PATH, help="Path for CSV export")
    args = parser.parse_args()

    print("=" * 80)
    print("EARNHAUS JOB & USERANALYTICS EXTRACTOR")
    print(f"Employer ID : {args.employer_id}")
    print(f"Population  : {args.pop_min:,} - {args.pop_max:,}")
    print(f"Time Window : Last {args.days} days")
    print(f"Target Jobs : {args.count} unique titles & locations")
    print("=" * 80)

    local_client = get_mongo_client()
    prod_db = get_remote_db(local_client, "prod_jobiak_ai")

    # 1. Load population lookup map
    loc_map = load_population_map(local_client, args.pop_min, args.pop_max)

    # 2. Extract matching jobs
    jobs = fetch_candidate_jobs(prod_db, args.employer_id, args.days, loc_map, args.count)

    if not jobs:
        print("[!] No matching jobs found with the specified criteria.")
        sys.exit(0)

    # 3. Lookup userAnalytics for each job
    print("\n" + "=" * 80)
    print("RESULTS & ANALYTICS SUMMARY")
    print("=" * 80)

    export_records = []
    for idx, job in enumerate(jobs, start=1):
        analytics = get_user_agent_analytics(prod_db, args.employer_id, job["jobId"])
        job["user_agents"] = analytics["distinct_user_agents"]
        export_records.append(job)

        print(f"\n[{idx}] TITLE: {job['title']}")
        print(f"    - Job ID          : {job['jobId']}")
        print(f"    - Location (Job)  : {job['location']}")
        print(f"    - Location (Old)  : {job['matched_location_str']}")
        print(f"    - Population      : {job['population']:,}")
        print(f"    - Date Posted     : {job['datePosted']}")
        print(f"    - Submitted URL   : {job['submittedUrl']}")
        print(f"    - Analytics Hits  : {analytics['total_hits']}")
        print(f"    - Firebase Count  : {analytics['firebase_count']}")
        print(f"    - Googlebot Count : {analytics['googlebot_count']}")
        print(f"    - Other Bots      : {analytics['other_bot_count']}")
        if analytics["distinct_user_agents"]:
            print(f"    - User Agents Seen:")
            for ua in analytics["distinct_user_agents"]:
                print(f"        * {ua}")

    # 4. Export CSV
    export_to_csv(export_records, args.csv_file)

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
