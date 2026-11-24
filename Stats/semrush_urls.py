import pymongo
import csv
import sys
import time
import os
import concurrent.futures
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

# --------------------------------------------------    
# CONFIGURATION
# --------------------------------------------------
LOCAL_MONGO_URI = os.getenv("MONGO_URI")
if not LOCAL_MONGO_URI:
    print("CRITICAL ERROR: MONGO_URI not set in environment")
    sys.exit(1)

CREDS_DB = "mongo_creds"

# DOMAINS TO PROCESS
DOMAINS = ["justopinionjobs_prod", "clerkcrew_prod", "directclients_prod"]

# CUSTOM SEMRUSH DOMAIN MAPPING (Overrides default naming logic)
CUSTOM_SEMRUSH_DOMAINS = {
    "directclients_prod": "apexfocusgroup.com"
}

# LOCAL DB CONFIG (For saving results)
LOCAL_DB = "domain_expires"
AUDIT_COLLECTION = "semrush_view_audit"

# SEMRUSH SOURCE CONFIG
SEMRUSH_MONGO_URI = os.getenv("SEMRUSH_MONGO_URI")
if not SEMRUSH_MONGO_URI:
    print("CRITICAL ERROR: SEMRUSH_MONGO_URI not set in environment")
    sys.exit(1)

SEMRUSH_DB_NAME = "domain_expires"
SEMRUSH_COLLECTION = "semrush_url's"
    
# PERFORMANCE CONFIG
BATCH_SIZE = 10000  # Process 10k URLs at a time
MAX_WORKERS = 10    # Parallel threads


# --------------------------------------------------
# UTILS
# --------------------------------------------------
def get_ist_date_str():
    """Returns current date in IST (UTC+5:30) formatted as YYYY-MM-DD."""
    ist_offset = timedelta(hours=5, minutes=30)
    ist_now = datetime.now(timezone.utc) + ist_offset
    return ist_now.strftime("%Y-%m-%d")


def get_downloads_path():
    """Constructs path to 'Downloads/Semrush URL's' safely."""
    user_home = os.path.expanduser("~")
    target_dir = os.path.join(user_home, "Downloads", "Semrush URL's")
    os.makedirs(target_dir, exist_ok=True)
    return target_dir


# --------------------------------------------------
# WORKER LOGIC
# --------------------------------------------------
def process_url_batch(batch_urls, mongo_uri, domain_db_name, domain_label, semrush_domain_filter):
    """
    Worker function to process a chunk of URLs.
    Returns: (list of audit records, list of csv rows, missing count)
    """
    if not batch_urls:
        return [], [], 0

    # Independent connection for thread safety with a timeout
    client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client[domain_db_name]

    audit_records = []
    csv_rows = []
    missing_count = 0

    try:
        # Batch Query for efficiency
        cursor = db["Target_P4_Opt"].find(
            {"submittedUrl": {"$in": batch_urls}},
            {"submittedUrl": 1, "view_exists": 1}
        )

        found_jobs = {}
        for doc in cursor:
            if "submittedUrl" in doc:
                found_jobs[doc["submittedUrl"]] = doc.get("view_exists", False)

        # Check results against the incoming batch
        for url in batch_urls:
            has_view_exists = found_jobs.get(url, False)

            # Record for DB
            record = {
                "domain": domain_label,
                "url": url,
                "semrush_domain": semrush_domain_filter,
                "has_view_exists": has_view_exists,
                "checked_at": datetime.now()
            }
            audit_records.append(record)

            # Record for CSV if missing
            if not has_view_exists:
                # CSV Format: [DB_Domain, Semrush_Domain, URL, Status]
                csv_rows.append([domain_label, semrush_domain_filter, url, "False/Not Found"])
                missing_count += 1

    except Exception as e:
        print(f"\n  [Worker Error in {domain_label}] {e}")
    finally:
        client.close()

    return audit_records, csv_rows, missing_count


# --------------------------------------------------
# MAIN PROCESS CONTROLLER
# --------------------------------------------------
def process_domain(domain, writer, local_db_col):
    """
    Orchestrates fetching and parallel processing for a domain.
    """
    # 1. Setup - Check for custom domain mapping first
    if domain in CUSTOM_SEMRUSH_DOMAINS:
        semrush_domain_filter = CUSTOM_SEMRUSH_DOMAINS[domain]
    else:
        base_name = domain.replace("_prod", "")
        semrush_domain_filter = f"{base_name}.com"
        
    print(f"\n[{domain}] Starting Analysis (Filter: {semrush_domain_filter})")

    # 2. Get Prod URI
    local_client = pymongo.MongoClient(LOCAL_MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        creds_db = local_client[CREDS_DB]
        creds = creds_db["creds"].find_one({"domain": domain}, {"mongo_uri": 1})
    except Exception as e:
        print(f"  ERROR fetching credentials for {domain}: {e}")
        local_client.close()
        return 0, 0
    finally:
        local_client.close()

    if not creds or "mongo_uri" not in creds:
        print(f"  ERROR: No mongo_uri found for {domain} in {CREDS_DB}")
        return 0, 0

    prod_uri = creds["mongo_uri"]

    # 3. Fetch Semrush URLs (Single thread, fast read)
    print(f"  Fetching Semrush URLs from source...")
    semrush_client = pymongo.MongoClient(SEMRUSH_MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        semrush_db = semrush_client[SEMRUSH_DB_NAME]
        semrush_cursor = semrush_db[SEMRUSH_COLLECTION].find(
            {"domain": semrush_domain_filter},
            {"url": 1}
        )
        all_urls = [doc["url"] for doc in semrush_cursor if "url" in doc]
    except Exception as e:
        print(f"  ERROR fetching URLs from SEMRUSH: {e}")
        semrush_client.close()
        return 0, 0
    finally:
        semrush_client.close()

    total_urls = len(all_urls)
    print(f"  Found {total_urls:,} URLs. Starting parallel workers ({MAX_WORKERS} threads)...")

    if total_urls == 0:
        return 0, 0

    # 4. Chunking
    chunks = [all_urls[i: i + BATCH_SIZE] for i in range(0, total_urls, BATCH_SIZE)]
    print(f"  Created {len(chunks)} chunks of size {BATCH_SIZE:,}.")

    # 5. Parallel Execution
    total_missing = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        futures = {
            executor.submit(
                process_url_batch,
                chunk,
                prod_uri,
                domain,
                domain,
                semrush_domain_filter
            ): chunk for chunk in chunks
        }

        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            try:
                batch_audit, batch_csv, batch_missing = future.result()

                # Write to DB
                if batch_audit:
                    local_db_col.insert_many(batch_audit)

                # Write to CSV
                if batch_csv:
                    writer.writerows(batch_csv)

                total_missing += batch_missing

                # Optional progress dot
                sys.stdout.write(".")
                sys.stdout.flush()

            except Exception as exc:
                print(f"\n  Worker exception during execution: {exc}")

    print(f"\n  Finished {domain}. URLs without view_exists: {total_missing:,}")
    return total_urls, total_missing


# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    start_time = time.time()

    # 1. Setup File Paths
    ist_date = get_ist_date_str()
    output_dir = get_downloads_path()
    csv_filename = os.path.join(output_dir, f"semrush_urls_{ist_date}.csv")

    print(f"========== SEMRUSH VIEW AUDIT STARTED ==========")
    print(f"Output Directory: {output_dir}")
    print(f"Output File     : {csv_filename}")
    print(f"Batch Size      : {BATCH_SIZE:,}")
    print(f"Workers         : {MAX_WORKERS}")
    print(f"Domains         : {DOMAINS}\n")

    # Connect to local DB for saving audit
    main_client = pymongo.MongoClient(LOCAL_MONGO_URI, serverSelectionTimeoutMS=5000)
    
    try:
        # Verify local connection before proceeding
        main_client.admin.command('ping')
        audit_col = main_client[LOCAL_DB][AUDIT_COLLECTION]

        total_processed = 0
        total_missing = 0

        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["DB_Domain", "Semrush_Domain", "URL", "View_Exists_Status"])

            for domain in DOMAINS:
                p_count, m_count = process_domain(domain, writer, audit_col)
                total_processed += p_count
                total_missing += m_count

    except pymongo.errors.ConnectionFailure:
        print("\nCRITICAL ERROR: Could not connect to the local MongoDB database. Please check MONGO_URI.")
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        main_client.close()

    elapsed = time.time() - start_time

    print(f"\n========== AUDIT COMPLETED in {elapsed:.2f}s ==========")
    print(f"Total URLs Checked : {total_processed:,}")
    print(f"No view_exists     : {total_missing:,}")
    print(f"CSV Location       : {csv_filename}")