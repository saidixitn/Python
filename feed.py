
import os
import logging
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

CREDS_DATABASE = "mongo_creds"
CREDS_COLLECTION = "creds"

PROD_DATABASE = "prod_jobiak_ai"
JOBICARE_DATABASE = "jobicarenode_prod"

JOBICARE_COLLECTION = "Target_P4_Opt"
JOB_COLLECTION = "job"

BATCH_SIZE = 2000
LOOKUP_BATCH_SIZE = 1000


# ============================================================
# CLIENT CONFIGURATION
# ============================================================

CLIENTS = {
    "ABS Kids": {
        "employer_id": "6aa8d214060e8f0b78b0dc87",
        "jicn_employer_id": "emp-jicn-abs",
    },
    "QRM": {
        "employer_id": "6a7b516d060e8f0b78b0dc5a",
        "jicn_employer_id": "emp-jicn-qrm",
    },
    "Concentrix": {
        "employer_id": "6a8871d1060e8f0b78b0dc69",
        "jicn_employer_id": "emp-jicn-concentrix",
    },
    "HCSG": {
        "employer_id": "6a904f26060e8f0b78b0dc81",
        "jicn_employer_id": "emp-jicn-hcsg",
    },
    "YES! Communities": {
        "employer_id": "6a86c3d7060e8f0b78b0dc66",
        "jicn_employer_id": "emp-jicn-yescommunities",
    },
}


# ============================================================
# FIELD CONFIGURATION
# ============================================================

EMPLOYER_FIELD = "employerId"
UNIQUE_KEY_FIELD = "uniqueKey"
FEED_DATA_FIELD = "extraInfo.feedData"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("posting_stats")


# ============================================================
# HELPERS
# ============================================================

def safe_text(value):
    if value is None:
        return ""

    return str(value).strip()


def chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def normalize_feed_data(value):
    """
    Returns:
        1    = Feed Job
        0    = Expanded Job
        None = Unknown / Missing
    """

    # Do not treat Python booleans as integer 1 or 0.
    if isinstance(value, bool):
        return None

    if value == 1 or value == "1":
        return 1

    if value == 0 or value == "0":
        return 0

    return None


def classify_records(records):
    """
    Classifies uniqueKey records.

    Duplicate records with the same feedData are counted once.
    Conflicting feedData values are classified as unknown.
    """

    feed_jobs = set()
    expanded_jobs = set()
    unknown_jobs = set()

    duplicate_records = 0
    conflicting_records = 0

    for unique_key, classifications in records.items():

        if len(classifications) > 1:
            duplicate_records += len(classifications) - 1

        valid_classifications = set(classifications)

        if len(valid_classifications) > 1:
            conflicting_records += 1
            unknown_jobs.add(unique_key)
            continue

        classification = next(iter(valid_classifications))

        if classification == 1:
            feed_jobs.add(unique_key)

        elif classification == 0:
            expanded_jobs.add(unique_key)

        else:
            unknown_jobs.add(unique_key)

    return {
        "feed_jobs": feed_jobs,
        "expanded_jobs": expanded_jobs,
        "unknown_jobs": unknown_jobs,
        "duplicate_records": duplicate_records,
        "conflicting_records": conflicting_records,
    }


# ============================================================
# MONGODB CONNECTION
# ============================================================

def connect_mongodb():

    if not MONGO_URI:
        raise ValueError("MONGO_URI is missing from .env")

    bootstrap = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=15000
    )

    try:
        bootstrap.admin.command("ping")

        creds_collection = bootstrap[
            CREDS_DATABASE
        ][CREDS_COLLECTION]

        # Production database URI
        prod_creds = creds_collection.find_one(
            {"domain": PROD_DATABASE},
            {"_id": 0, "mongo_uri": 1}
        )

        if not prod_creds or not prod_creds.get("mongo_uri"):
            raise ValueError(
                f"Mongo URI not found for {PROD_DATABASE}"
            )

        # Jobicare database URI
        jobicare_creds = creds_collection.find_one(
            {"domain": JOBICARE_DATABASE},
            {"_id": 0, "mongo_uri": 1}
        )

        if not jobicare_creds or not jobicare_creds.get("mongo_uri"):
            raise ValueError(
                f"Mongo URI not found for {JOBICARE_DATABASE}"
            )

        # Connect to production
        prod_client = MongoClient(
            prod_creds["mongo_uri"],
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000
        )

        prod_client.admin.command("ping")

        # Connect to Jobicare
        jobicare_client = MongoClient(
            jobicare_creds["mongo_uri"],
            serverSelectionTimeoutMS=15000,
            connectTimeoutMS=15000
        )

        jobicare_client.admin.command("ping")

    finally:
        bootstrap.close()

    logger.info("Connected to %s", PROD_DATABASE)
    logger.info("Connected to %s", JOBICARE_DATABASE)

    return (
        prod_client,
        prod_client[PROD_DATABASE],
        jobicare_client,
        jobicare_client[JOBICARE_DATABASE]
    )


# ============================================================
# STEP 1: FETCH PRODUCTION JOBS
# ============================================================

def fetch_production_jobs(database, client_name, config):

    employer_id = config["employer_id"]

    projection = {
        "_id": 0,
        "clientJobId": 1,
        "jobId": 1,
        "jobPubJobId": 1,
        "title": 1,
    }

    cursor = database[JOB_COLLECTION].find(
        {
            "employerId": employer_id
        },
        projection,
        batch_size=BATCH_SIZE
    )

    client_job_ids = set()

    total_jobs = 0
    missing_client_job_ids = 0

    try:
        for job in cursor:

            total_jobs += 1

            client_job_id = safe_text(
                job.get("clientJobId")
            )

            if not client_job_id:
                missing_client_job_ids += 1
                continue

            client_job_ids.add(client_job_id)

    finally:
        cursor.close()

    logger.info(
        "%s | Production jobs: %s | Unique clientJobIds: %s",
        client_name,
        total_jobs,
        len(client_job_ids)
    )

    return {
        "total_jobs": total_jobs,
        "client_job_ids": client_job_ids,
        "missing_client_job_ids": missing_client_job_ids,
    }


# ============================================================
# STEP 2: MATCH PRODUCTION JOBS WITH JOBICARE
# ============================================================

def fetch_jobicare_jobs(
    database,
    client_name,
    config,
    client_job_ids
):

    jicn_employer_id = config["jicn_employer_id"]

    results = {}

    if not client_job_ids:
        return results

    unique_keys = list(client_job_ids)

    collection = database[JOBICARE_COLLECTION]

    for batch_number, batch in enumerate(
        chunks(unique_keys, LOOKUP_BATCH_SIZE),
        start=1
    ):

        # IMPORTANT:
        # Jobicare employerId must contain the JICN employer ID.
        query = {
            "employerId": jicn_employer_id,
            "uniqueKey": {
                "$in": batch
            }
        }

        projection = {
            "_id": 0,
            "uniqueKey": 1,
            "extraInfo.feedData": 1,
        }

        cursor = collection.find(
            query,
            projection,
            batch_size=BATCH_SIZE
        )

        try:
            for document in cursor:

                unique_key = safe_text(
                    document.get("uniqueKey")
                )

                if not unique_key:
                    continue

                extra_info = document.get("extraInfo")

                feed_data = normalize_feed_data(
                    extra_info.get("feedData")
                    if isinstance(extra_info, dict)
                    else None
                )

                results.setdefault(
                    unique_key, []
                ).append(feed_data)

        finally:
            cursor.close()

        logger.info(
            "%s | Matching batch %s completed | Keys checked: %s",
            client_name,
            batch_number,
            len(batch)
        )

    return results


# ============================================================
# STEP 3: FETCH JOBS ELIGIBLE FOR POSTING
# ============================================================

def fetch_jobs_to_post(
    database,
    client_name,
    config,
    posted_job_ids
):
    """
    Fetch eligible Jobicare jobs that are not already present
    in production.

    Query logic:

    {
        "employerId": jicn_employer_id,
        "job_status": {"$ne": 3},
        "gpost": {"$in": [1, 3]},
        "uniqueKey": {"$nin": posted_job_ids}
    }

    feedData:
        1 = Feed Job to Post
        0 = Expanded Job to Post
    """

    jicn_employer_id = config["jicn_employer_id"]

    collection = database[JOBICARE_COLLECTION]

    query = {
        "employerId": jicn_employer_id,
        "job_status": {
            "$ne": 3
        },
        "gpost": {
            "$in": [1, 3]
        },
        "uniqueKey": {
            "$nin": list(posted_job_ids)
        }
    }

    projection = {
        "_id": 0,
        "uniqueKey": 1,
        "extraInfo.feedData": 1,
    }

    logger.info(
        "%s | Fetching eligible jobs to post...",
        client_name
    )

    cursor = collection.find(
        query,
        projection,
        batch_size=BATCH_SIZE
    )

    eligible_records = {}

    total_eligible_records = 0

    try:
        for document in cursor:

            total_eligible_records += 1

            unique_key = safe_text(
                document.get("uniqueKey")
            )

            if not unique_key:
                continue

            extra_info = document.get("extraInfo")

            feed_data = normalize_feed_data(
                extra_info.get("feedData")
                if isinstance(extra_info, dict)
                else None
            )

            eligible_records.setdefault(
                unique_key, []
            ).append(feed_data)

    finally:
        cursor.close()

    classified = classify_records(eligible_records)

    feed_jobs_to_post = len(
        classified["feed_jobs"]
    )

    expanded_jobs_to_post = len(
        classified["expanded_jobs"]
    )

    logger.info(
        "%s | Eligible Jobicare records: %s | Unique keys: %s",
        client_name,
        total_eligible_records,
        len(eligible_records)
    )

    return {
        "total_eligible_records": total_eligible_records,
        "unique_eligible_jobs": len(eligible_records),
        "feed_jobs_to_post": feed_jobs_to_post,
        "expanded_jobs_to_post": expanded_jobs_to_post,
        "unknown_jobs_to_post": len(
            classified["unknown_jobs"]
        ),
        "duplicate_records_to_post": classified[
            "duplicate_records"
        ],
        "conflicting_records_to_post": classified[
            "conflicting_records"
        ],
    }


# ============================================================
# STEP 4: CALCULATE POSTING STATISTICS
# ============================================================

def calculate_posting_stats(
    production_data,
    jobicare_data,
    jobs_to_post_data
):

    classified = classify_records(jobicare_data)

    feed_jobs = classified["feed_jobs"]
    expanded_jobs = classified["expanded_jobs"]
    unknown_jobs = classified["unknown_jobs"]

    production_ids = production_data["client_job_ids"]

    matched_jobs = len(
        production_ids.intersection(jobicare_data.keys())
    )

    not_found_jobs = len(
        production_ids.difference(jobicare_data.keys())
    )

    unknown_feed_data = len(
        unknown_jobs
    )

    return {

        "total_jobs": production_data["total_jobs"],

        "unique_client_job_ids": len(
            production_ids
        ),

        "missing_client_job_ids": production_data[
            "missing_client_job_ids"
        ],

        "matched_jobs": matched_jobs,

        "feed_jobs": len(feed_jobs),

        "expanded_jobs": len(expanded_jobs),

        "not_found_jobs": not_found_jobs,

        "unknown_feed_data": unknown_feed_data,

        "duplicate_records": classified[
            "duplicate_records"
        ],

        "conflicting_records": classified[
            "conflicting_records"
        ],

        "feed_jobs_to_post": jobs_to_post_data[
            "feed_jobs_to_post"
        ],

        "expanded_jobs_to_post": jobs_to_post_data[
            "expanded_jobs_to_post"
        ],

        "unknown_jobs_to_post": jobs_to_post_data[
            "unknown_jobs_to_post"
        ],

        "total_eligible_jobs": jobs_to_post_data[
            "unique_eligible_jobs"
        ],

        "duplicate_records_to_post": jobs_to_post_data[
            "duplicate_records_to_post"
        ],

        "conflicting_records_to_post": jobs_to_post_data[
            "conflicting_records_to_post"
        ],

    }


# ============================================================
# STEP 5: PRINT CLIENT STATISTICS
# ============================================================

def print_client_stats(client_name, stats):

    print("\n" + "=" * 75)
    print(f"CLIENT: {client_name}")
    print("=" * 75)

    print(f"{'Metric':<45} {'Count':>15}")
    print("-" * 62)

    metrics = [

        ("Total Production Jobs", stats["total_jobs"]),

        ("Unique Client Job IDs", stats["unique_client_job_ids"]),

        ("Missing Client Job IDs", stats["missing_client_job_ids"]),

        ("Matched Jobs in Jobicare", stats["matched_jobs"]),

        ("Feed Jobs", stats["feed_jobs"]),

        ("Expanded Jobs", stats["expanded_jobs"]),

        ("Jobs Not Found in Jobicare", stats["not_found_jobs"]),

        ("Unknown Feed Data", stats["unknown_feed_data"]),

        ("Duplicate Jobicare Records", stats["duplicate_records"]),

        ("Conflicting Feed Data Records", stats["conflicting_records"]),

    ]

    for label, value in metrics:
        print(f"{label:<45} {value:>15,}")

    print("-" * 62)

    classified = (
        stats["feed_jobs"]
        + stats["expanded_jobs"]
    )

    print(f"{'Total Classified Jobs':<45} {classified:>15,}")

    print("\n" + "-" * 62)
    print("                 JOBS TO POST")
    print("-" * 62)

    post_metrics = [

        ("Total Eligible Unique Jobs", stats["total_eligible_jobs"]),

        ("Feed Jobs to Post", stats["feed_jobs_to_post"]),

        ("Expanded Jobs to Post", stats["expanded_jobs_to_post"]),

        ("Unknown Jobs to Post", stats["unknown_jobs_to_post"]),

        ("Duplicate Eligible Records", stats["duplicate_records_to_post"]),

        ("Conflicting Eligible Records", stats["conflicting_records_to_post"]),

    ]

    for label, value in post_metrics:
        print(f"{label:<45} {value:>15,}")

    print("-" * 62)

    if stats["unique_client_job_ids"]:

        feed_percentage = (
            stats["feed_jobs"]
            / stats["unique_client_job_ids"]
        ) * 100

        expanded_percentage = (
            stats["expanded_jobs"]
            / stats["unique_client_job_ids"]
        ) * 100

        print(f"{'Feed Job %':<45} {feed_percentage:>14.2f}%")

        print(f"{'Expanded Job %':<45} {expanded_percentage:>14.2f}%")

    print("=" * 75)


# ============================================================
# STEP 6: PRINT COMBINED STATISTICS
# ============================================================

def print_total_stats(all_stats):

    total = defaultdict(int)

    numeric_keys = [

        "total_jobs",
        "unique_client_job_ids",
        "missing_client_job_ids",
        "matched_jobs",
        "feed_jobs",
        "expanded_jobs",
        "not_found_jobs",
        "unknown_feed_data",
        "duplicate_records",
        "conflicting_records",
        "feed_jobs_to_post",
        "expanded_jobs_to_post",
        "unknown_jobs_to_post",
        "total_eligible_jobs",
        "duplicate_records_to_post",
        "conflicting_records_to_post",

    ]

    for stats in all_stats.values():

        for key in numeric_keys:
            total[key] += stats[key]

    print("\n\n")

    print("#" * 75)
    print("                 OVERALL POSTING STATISTICS")
    print("#" * 75)

    print(f"{'Metric':<45} {'Count':>15}")
    print("-" * 62)

    metrics = [

        ("Total Production Jobs", total["total_jobs"]),

        ("Unique Client Job IDs", total["unique_client_job_ids"]),

        ("Missing Client Job IDs", total["missing_client_job_ids"]),

        ("Matched Jobs in Jobicare", total["matched_jobs"]),

        ("Feed Jobs", total["feed_jobs"]),

        ("Expanded Jobs", total["expanded_jobs"]),

        ("Jobs Not Found in Jobicare", total["not_found_jobs"]),

        ("Unknown Feed Data", total["unknown_feed_data"]),

        ("Duplicate Jobicare Records", total["duplicate_records"]),

        ("Conflicting Feed Data Records", total["conflicting_records"]),

    ]

    for label, value in metrics:
        print(f"{label:<45} {value:>15,}")

    print("-" * 62)

    classified = (
        total["feed_jobs"]
        + total["expanded_jobs"]
    )

    print(f"{'Total Classified Jobs':<45} {classified:>15,}")

    print("\n" + "-" * 62)
    print("                 OVERALL JOBS TO POST")
    print("-" * 62)

    post_metrics = [

        ("Total Eligible Unique Jobs", total["total_eligible_jobs"]),

        ("Feed Jobs to Post", total["feed_jobs_to_post"]),

        ("Expanded Jobs to Post", total["expanded_jobs_to_post"]),

        ("Unknown Jobs to Post", total["unknown_jobs_to_post"]),

        ("Duplicate Eligible Records", total["duplicate_records_to_post"]),

        ("Conflicting Eligible Records", total["conflicting_records_to_post"]),

    ]

    for label, value in post_metrics:
        print(f"{label:<45} {value:>15,}")

    print("-" * 62)

    if total["unique_client_job_ids"]:

        feed_percentage = (
            total["feed_jobs"]
            / total["unique_client_job_ids"]
        ) * 100

        expanded_percentage = (
            total["expanded_jobs"]
            / total["unique_client_job_ids"]
        ) * 100

        print(f"{'Feed Job %':<45} {feed_percentage:>14.2f}%")

        print(f"{'Expanded Job %':<45} {expanded_percentage:>14.2f}%")

    print("#" * 75)


# ============================================================
# MAIN EXECUTION
# ============================================================

def main():

    prod_client = None
    jobicare_client = None

    start_time = datetime.now()

    try:

        logger.info("=" * 70)
        logger.info("JOBIAK POSTING STATISTICS STARTED")
        logger.info("=" * 70)

        (
            prod_client,
            prod_database,
            jobicare_client,
            jobicare_database
        ) = connect_mongodb()

        all_stats = {}

        print("\n")
        print("#" * 75)
        print("                 JOBIAK POSTING STATISTICS")
        print("#" * 75)

        for client_name, config in CLIENTS.items():

            print(f"\nProcessing {client_name}...")

            # ------------------------------------------------
            # STEP 1: Fetch all production jobs.
            # These clientJobIds represent already-posted jobs.
            # ------------------------------------------------

            production_data = fetch_production_jobs(
                prod_database,
                client_name,
                config
            )

            posted_job_ids = production_data[
                "client_job_ids"
            ]

            logger.info(
                "%s | Posted job IDs collected: %s",
                client_name,
                len(posted_job_ids)
            )

            # ------------------------------------------------
            # STEP 2: Match production IDs in Jobicare.
            # ------------------------------------------------

            jobicare_data = fetch_jobicare_jobs(
                jobicare_database,
                client_name,
                config,
                posted_job_ids
            )

            # ------------------------------------------------
            # STEP 3: Find eligible jobs to post.
            # Exclude every production clientJobId.
            # ------------------------------------------------

            jobs_to_post_data = fetch_jobs_to_post(
                jobicare_database,
                client_name,
                config,
                posted_job_ids
            )

            # ------------------------------------------------
            # STEP 4: Calculate statistics.
            # ------------------------------------------------

            stats = calculate_posting_stats(
                production_data,
                jobicare_data,
                jobs_to_post_data
            )

            all_stats[client_name] = stats

            # ------------------------------------------------
            # STEP 5: Print client statistics.
            # ------------------------------------------------

            print_client_stats(
                client_name,
                stats
            )

        # ----------------------------------------------------
        # STEP 6: Print combined statistics.
        # ----------------------------------------------------

        print_total_stats(all_stats)

        elapsed = datetime.now() - start_time

        print(f"\nCompleted successfully in {elapsed}")

        logger.info("=" * 70)
        logger.info("POSTING STATISTICS COMPLETED")
        logger.info("=" * 70)

    except Exception:

        logger.exception("Posting statistics failed")
        raise

    finally:

        if prod_client:
            prod_client.close()

        if jobicare_client:
            jobicare_client.close()

        logger.info("MongoDB connections closed.")


if __name__ == "__main__":
    main()
