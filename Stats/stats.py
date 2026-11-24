from pymongo import MongoClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import traceback
import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# LOCAL CONNECTION
# =========================================================

LOCAL_MONGO_URI = os.getenv(
    "MONGO_URI_LOCAL",
    "mongodb://localhost:27017"
)

local_client = MongoClient(LOCAL_MONGO_URI)

# =========================================================
# DAILY STATS DB
# =========================================================

daily_stats_db = local_client["daily_stats"]

input_col = daily_stats_db["input"]

output_col = daily_stats_db["output"]

# =========================================================
# CREDS DB
# =========================================================

creds_db = local_client["mongo_creds"]

creds_col = creds_db["creds"]

# =========================================================
# CACHE
# =========================================================

DB_CACHE = {}
CLIENT_CACHE = {}

MAX_WORKERS = 10

# =========================================================
# DATES
# =========================================================

UTC = timezone.utc

today = datetime.now(UTC).replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0
)

tomorrow = today + timedelta(days=1)

yesterday = today - timedelta(days=1)

five_days_future = today + timedelta(days=5)

# =========================================================
# GET DATABASE
# =========================================================

def get_database(domain, domain_type):

    try:

        # =================================================
        # DB NAME
        # =================================================

        if domain_type == "Proxy":

            db_name = "prod_jobiak_ai"

        elif domain_type == "Direct Apply":

            db_name = "directclients_prod"

        elif domain_type == "Programmatic":

            base_domain = domain.replace("www.", "")
            base_domain = base_domain.split(".")[0]

            db_name = f"{base_domain}_prod"

        else:

            return None

        # =================================================
        # CACHE
        # =================================================

        if db_name in DB_CACHE:

            return DB_CACHE[db_name]

        # =================================================
        # FETCH MONGO URI
        # =================================================

        creds = creds_col.find_one(
            {
                "domain": db_name
            },
            {
                "_id": 0,
                "mongo_uri": 1
            }
        )

        if not creds:

            print(f"Mongo URI not found for {db_name}")

            return None

        mongo_uri = creds["mongo_uri"]

        # =================================================
        # CONNECT
        # =================================================

        client = MongoClient(mongo_uri)

        db = client[db_name]

        CLIENT_CACHE[db_name] = client
        DB_CACHE[db_name] = db

        print(f"CONNECTED : {db_name}")

        return db

    except Exception:

        print(traceback.format_exc())

        return None

# =========================================================
# COLLECTIONS
# =========================================================

def get_collections(db, domain_type):

    # =====================================================
    # PROXY
    # =====================================================

    if domain_type == "Proxy":

        return {

            "jobs": db["job"],

            "analytics": db["userAnalytics"],

            "proxy_logs": db["jobsGoogleSubmittedLog"]
        }

    # =====================================================
    # PROGRAMMATIC + DIRECT APPLY
    # =====================================================

    return {

        "jobs": db["Target_P4_Opt"],

        "analytics": db["userAnalytics"],

        "queue": db["aj_jp_jobqueue"],

        "logs": db["aj_jp_google_logs"]
    }

# =========================================================
# EMPLOYER FILTER
# =========================================================

def build_employer_filter(domain_type, employer_id):

    if domain_type == "Programmatic":

        return {}

    return {
        "employerId": employer_id
    }

# =========================================================
# COMPANY STATS
# =========================================================

def get_company_stats(
    collection,
    match_filter,
    company_field="company",
    employer_field="employerId"
):

    pipeline = [

        {
            "$match": match_filter
        },

        {
            "$group": {

                "_id": {

                    "company": {
                        "$ifNull": [
                            f"${company_field}",
                            "Unknown"
                        ]
                    },

                    "employerId": {
                        "$ifNull": [
                            f"${employer_field}",
                            ""
                        ]
                    }
                },

                "count": {
                    "$sum": 1
                }
            }
        },

        {
            "$project": {

                "_id": 0,

                "company": "$_id.company",

                "employerId": "$_id.employerId",

                "count": 1
            }
        },

        {
            "$sort": {
                "count": -1
            }
        }
    ]

    return list(
        collection.aggregate(
            pipeline,
            allowDiskUse=True
        )
    )

# =========================================================
# CACHE UPDATED COMPANIES
# =========================================================

def build_cache_updated_companies(
    source_companies,
    google_companies
):

    cache_updated_companies = []

    source_map = {

        (
            item["company"],
            item["employerId"]
        ): item["count"]

        for item in source_companies
    }

    google_map = {

        (
            item["company"],
            item["employerId"]
        ): item["count"]

        for item in google_companies
    }

    all_keys = (
        set(source_map.keys()) |
        set(google_map.keys())
    )

    for key in all_keys:

        source_count = source_map.get(key, 0)

        google_count = google_map.get(key, 0)

        diff = source_count - google_count

        if diff > 0:

            cache_updated_companies.append({

                "company": key[0],

                "employerId": key[1],

                "count": diff
            })

    cache_updated_companies.sort(
        key=lambda x: x["count"],
        reverse=True
    )

    return cache_updated_companies

# =========================================================
# REGULAR STATS
# =========================================================

def get_regular_stats(cols, employer_id, domain_type):

    jobs = cols["jobs"]

    analytics = cols["analytics"]

    logs = cols["logs"]

    base_filter = build_employer_filter(
        domain_type,
        employer_id
    )

    # =====================================================
    # TO POST
    # =====================================================

    to_post = jobs.count_documents({

        **base_filter,

        "gpost": 1,

        "job_status": {
            "$ne": 3
        }
    })

    # =====================================================
    # POSTED JOBS
    # =====================================================

    posted_filter = {

        **base_filter,

        "action": "post",

        "gpost": 5,

        "job_status": {
            "$ne": 3
        },

        "gpost_date": {
            "$gte": yesterday,
            "$lt": today
        }
    }

    posted_jobs = jobs.count_documents(
        posted_filter
    )

    posted_companies = get_company_stats(
        jobs,
        posted_filter
    )

    # =====================================================
    # UPDATED JOBS
    # =====================================================

    updated_filter = {

        **base_filter,

        "action": "update",

        "gpost": 5,

        "job_status": {
            "$ne": 3
        },

        "gpost_date": {
            "$gte": yesterday,
            "$lt": today
        }
    }

    updated_jobs = jobs.count_documents(
        updated_filter
    )

    updated_companies = get_company_stats(
        jobs,
        updated_filter
    )

    # =====================================================
    # REPOSTS
    # =====================================================

    repost_filter = {

        **base_filter,

        "action": "repost",

        "gpost": 5,

        "job_status": {
            "$ne": 3
        },

        "gpost_date": {
            "$gte": yesterday,
            "$lt": today
        }
    }

    reposts = jobs.count_documents(
        repost_filter
    )

    repost_companies = get_company_stats(
        jobs,
        repost_filter
    )

    # =====================================================
    # GOOGLE URL UPDATED
    # =====================================================

    google_updated_filter = {

        **base_filter,

        "callType": "URL_UPDATED",

        "createdAt": {
            "$gte": yesterday,
            "$lt": today
        }
    }

    google_updated_jobs = logs.count_documents(
        google_updated_filter
    )

    google_updated_companies = get_company_stats(
        logs,
        google_updated_filter,
        company_field="company",
        employer_field="employerId"
    )

    # =====================================================
    # CACHE UPDATED
    # =====================================================

    cache_source_jobs = (
        posted_jobs +
        updated_jobs +
        reposts
    )

    cache_updated_jobs = max(
        cache_source_jobs - google_updated_jobs,
        0
    )

    combined_source = {}

    for item in (
        posted_companies +
        updated_companies +
        repost_companies
    ):

        key = (
            item["company"],
            item["employerId"]
        )

        if key not in combined_source:

            combined_source[key] = {

                "company": item["company"],

                "employerId": item["employerId"],

                "count": 0
            }

        combined_source[key]["count"] += item["count"]

    cache_updated_companies = build_cache_updated_companies(
        list(combined_source.values()),
        google_updated_companies
    )

    # =====================================================
    # POSTED IDS
    # =====================================================

    posted_ids = jobs.distinct(
        "jobPubJobId",
        {
            **base_filter,

            "gpost": 5,

            "gpost_date": {
                "$gte": yesterday,
                "$lt": today
            }
        }
    )

    # =====================================================
    # POSTED BOT
    # =====================================================

    posted_bot = len(

        analytics.distinct(

            "jobPubJobId",

            {
                "jobPubJobId": {
                    "$in": posted_ids
                },

                "isBot": True,

                "action": {
                    "$in": [
                        "post",
                        "repost",
                        "update"
                    ]
                },

                "createdDt": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        )
    )

    # =====================================================
    # EXPIRED JOBS
    # =====================================================

    expired_filter = {

        **base_filter,

        "callType": "URL_DELETED",

        "createdAt": {
            "$gte": yesterday,
            "$lt": today
        }
    }

    expired_jobs = logs.count_documents(
        expired_filter
    )

    expired_companies = get_company_stats(
        logs,
        expired_filter,
        company_field="company",
        employer_field="employerId"
    )

    expired_ids = jobs.distinct(
        "jobPubJobId",
        {
            **base_filter,

            "gpost": 6,

            "gpost_expire_date": {
                "$gte": yesterday,
                "$lt": today
            }
        }
    )

    # =====================================================
    # EXPIRES BOT
    # =====================================================

    expires_bot = len(

        analytics.distinct(

            "jobPubJobId",

            {
                "jobPubJobId": {
                    "$in": expired_ids
                },

                "isBot": True,

                "action": "expire",

                "createdDt": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        )
    )

    # =====================================================
    # FEED EXPIRED JOBS
    # =====================================================

    feed_expires = jobs.count_documents({

        **base_filter,

        "job_status": 3
    })

    # =====================================================
    # DB CLICKS
    # =====================================================

    clicks_pipeline = [

        {
            "$match": {

                **base_filter,

                "isBot": False,

                "browserType": {
                    "$ne": "Unknown"
                },

                "deviceType": {
                    "$ne": "Unknown"
                },

                "isFromGoogle": True,

                "createdDt": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        },

        {
            "$group": {
                "_id": {
                    "ip": "$ipAddress",
                    "job": "$jobPubJobId"
                }
            }
        },

        {
            "$count": "count"
        }
    ]

    clicks_result = list(
        analytics.aggregate(
            clicks_pipeline,
            allowDiskUse=True
        )
    )

    db_clicks = (
        clicks_result[0]["count"]
        if clicks_result else 0
    )

    # =====================================================
    # BOT VISITS
    # =====================================================

    bot_visits = analytics.count_documents({

        **base_filter,

        "isBot": True,

        "createdDt": {
            "$gte": yesterday,
            "$lt": today
        }
    })

    # =====================================================
    # POSTING QUEUE
    # =====================================================

    posting_queue = jobs.count_documents({

        **base_filter,

        "gpost": 3,

        "job_status": {
            "$ne": 3
        }
    })

    # =====================================================
    # EXPIRES QUEUE
    # =====================================================

    expires_queue = jobs.count_documents({

        **base_filter,

        "gpost": 8
    })

    # =====================================================
    # POST FAIL
    # =====================================================

    post_fail = jobs.count_documents({

        **base_filter,

        "gpost": 4,

        "gpostExeOn": {
            "$exists": True
        }
    })

    # =====================================================
    # EXPIRES FAIL
    # =====================================================

    expires_fail = logs.count_documents({

        **base_filter,

        "callType": "URL_DELETED",

        "status_update": 4,

        "createdAt": {
            "$gte": yesterday,
            "$lt": today
        }
    })

    # =====================================================
    # TO EXPIRE IN 5 DAYS
    # =====================================================

    to_expire_5days = jobs.count_documents({

        **base_filter,

        "pub_expired": {
            "$lt": five_days_future
        },

        "gpost": 5,

        "job_status": {
            "$ne": 3
        }
    })

    # =====================================================
    # TOTAL POSTED JOBS
    # =====================================================

    total_posted_jobs = jobs.count_documents({

        **base_filter,

        "gpost": 5,

        "job_status": {
            "$ne": 3
        }
    })

    # =====================================================
    # TOTAL EXPIRED JOBS
    # =====================================================

    total_expired_jobs = jobs.count_documents({

        **base_filter,

        "gpost": 6
    })

    return {

        "To_Post": to_post,

        "Posted_Jobs": posted_jobs,

        "posted_companies": posted_companies,

        "Updated_Jobs": updated_jobs,

        "updated_companies": updated_companies,

        "Cache_Updated_Jobs": cache_updated_jobs,

        "cache_updated_companies": cache_updated_companies,

        "Google_Updated_Jobs": google_updated_jobs,

        "Expired_Jobs": expired_jobs,

        "expired_companies": expired_companies,

        "Posted_Bot": posted_bot,

        "Expires_Bot": expires_bot,

        "FeedExpiredJobs": feed_expires,

        "DB_Clicks": db_clicks,

        "Bot_Visits": bot_visits,

        "Posting_Queue": posting_queue,

        "Expires_Queue": expires_queue,

        "Post_Fail": post_fail,

        "Expires_Fail": expires_fail,

        "To_Expire_In_5Days": to_expire_5days,

        "Reposts": reposts,

        "Total Posted Job": total_posted_jobs,

        "Total Expired Jobs": total_expired_jobs
    }

# =========================================================
# PROXY STATS
# =========================================================

def get_proxy_stats(cols, employer_id):

    jobs = cols["jobs"]

    analytics = cols["analytics"]

    # =====================================================
    # TO POST
    # =====================================================

    to_post = jobs.count_documents({

        "employerId": employer_id,

        "isActive": False,

        "status": "new"
    })

    # =====================================================
    # PIPELINE
    # =====================================================

    pipeline = [

        {
            "$match": {

                "employerId": employer_id,

                "status": "posted",

                "isActive": True,

                "datePosted": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        },

        {
            "$lookup": {

                "from": "jobsGoogleSubmittedLog",

                "let": {
                    "jobId": "$jobId"
                },

                "pipeline": [

                    {
                        "$match": {
                            "$expr": {
                                "$and": [

                                    {
                                        "$eq": [
                                            "$jobId",
                                            "$$jobId"
                                        ]
                                    },

                                    {
                                        "$eq": [
                                            "$callType",
                                            "URL_UPDATED"
                                        ]
                                    }

                                ]
                            }
                        }
                    },

                    {
                        "$project": {
                            "_id": 1,
                            "createdAt": 1
                        }
                    }

                ],

                "as": "allLogs"
            }
        },

        {
            "$addFields": {

                "todayLogs": {

                    "$filter": {

                        "input": "$allLogs",

                        "as": "log",

                        "cond": {

                            "$and": [

                                {
                                    "$gte": [
                                        "$$log.createdAt",
                                        yesterday
                                    ]
                                },

                                {
                                    "$lt": [
                                        "$$log.createdAt",
                                        today
                                    ]
                                }

                            ]
                        }
                    }
                }
            }
        },

        {
            "$lookup": {

                "from": "job",

                "let": {
                    "clientJobId": "$clientJobId"
                },

                "pipeline": [

                    {
                        "$match": {

                            "status": "removed",

                            "$expr": {
                                "$eq": [
                                    "$clientJobId",
                                    "$$clientJobId"
                                ]
                            }
                        }
                    },

                    {
                        "$limit": 1
                    }

                ],

                "as": "removedHistory"
            }
        },

        {
            "$addFields": {

                "totalLogCount": {
                    "$size": "$allLogs"
                },

                "todayLogCount": {
                    "$size": "$todayLogs"
                },

                "hasRemovedHistory": {

                    "$gt": [

                        {
                            "$size": "$removedHistory"
                        },

                        0
                    ]
                }
            }
        },

        {
            "$addFields": {

                "classification": {

                    "$switch": {

                        "branches": [

                            {
                                "case": {

                                    "$and": [

                                        {
                                            "$gt": [
                                                "$totalLogCount",
                                                1
                                            ]
                                        },

                                        {
                                            "$gt": [
                                                "$todayLogCount",
                                                0
                                            ]
                                        }

                                    ]
                                },

                                "then": "update"
                            },

                            {
                                "case": {

                                    "$and": [

                                        {
                                            "$eq": [
                                                "$totalLogCount",
                                                1
                                            ]
                                        },

                                        "$hasRemovedHistory",

                                        {
                                            "$gt": [
                                                "$todayLogCount",
                                                0
                                            ]
                                        }

                                    ]
                                },

                                "then": "repost"
                            },

                            {
                                "case": {

                                    "$and": [

                                        {
                                            "$eq": [
                                                "$totalLogCount",
                                                1
                                            ]
                                        },

                                        {
                                            "$eq": [
                                                "$hasRemovedHistory",
                                                False
                                            ]
                                        },

                                        {
                                            "$gt": [
                                                "$todayLogCount",
                                                0
                                            ]
                                        }

                                    ]
                                },

                                "then": "posting"
                            }

                        ],

                        "default": "cache_update"
                    }
                }
            }
        }

    ]

    classified_jobs = list(
        jobs.aggregate(
            pipeline,
            allowDiskUse=True
        )
    )

    postings = 0

    reposts = 0

    updates = 0

    cache_updates = 0

    posted_companies = []

    updated_companies = []

    cache_updated_companies = []

    expired_companies = []

    posting_map = {}

    update_map = {}

    cache_map = {}

    # =====================================================
    # COUNTS
    # =====================================================

    for job in classified_jobs:

        classification = job.get(
            "classification"
        )

        company = job.get(
            "company",
            "Unknown"
        )

        key = (
            company,
            employer_id
        )

        if classification == "posting":

            postings += 1

            posting_map[key] = (
                posting_map.get(key, 0) + 1
            )

        elif classification == "update":

            updates += 1

            update_map[key] = (
                update_map.get(key, 0) + 1
            )

        elif classification == "repost":

            reposts += 1

        else:

            cache_updates += 1

            cache_map[key] = (
                cache_map.get(key, 0) + 1
            )

    # =====================================================
    # COMPANY LISTS
    # =====================================================

    for key, count in posting_map.items():

        posted_companies.append({

            "company": key[0],

            "employerId": key[1],

            "count": count
        })

    for key, count in update_map.items():

        updated_companies.append({

            "company": key[0],

            "employerId": key[1],

            "count": count
        })

    for key, count in cache_map.items():

        cache_updated_companies.append({

            "company": key[0],

            "employerId": key[1],

            "count": count
        })

    # =====================================================
    # EXPIRED JOBS
    # =====================================================

    expired_filter = {

        "employerId": employer_id,

        "status": "removed",

        "isActive": False,

        "updatedAt": {
            "$gte": yesterday,
            "$lt": today
        }
    }

    expired_jobs = jobs.count_documents(
        expired_filter
    )

    expired_companies = get_company_stats(
        jobs,
        expired_filter
    )

    expired_ids = jobs.distinct(
        "jobId",
        expired_filter
    )

    # =====================================================
    # EXPIRES BOT
    # =====================================================

    expires_bot = len(

        analytics.distinct(

            "childJobId",

            {
                "childJobId": {
                    "$in": expired_ids
                },

                "isBot": True,

                "country": "United States",

                "createdDt": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        )
    )

    # =====================================================
    # POSTED IDS
    # =====================================================

    posted_ids = jobs.distinct(

        "jobId",

        {

            "employerId": employer_id,

            "status": "posted",

            "isActive": True,

            "datePosted": {
                "$gte": yesterday,
                "$lt": today
            }
        }
    )

    # =====================================================
    # POSTED BOT
    # =====================================================

    posted_bot = len(

        analytics.distinct(

            "childJobId",

            {
                "childJobId": {
                    "$in": posted_ids
                },

                "isBot": True,

                "country": "United States",

                "createdDt": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        )
    )

    # =====================================================
    # FEED EXPIRED JOBS
    # =====================================================

    feed_expires = jobs.count_documents({

        "employerId": employer_id,

        "isActive": False,

        "status": "removed"
    })

    # =====================================================
    # DB CLICKS
    # =====================================================

    clicks_pipeline = [

        {
            "$match": {

                "employerId": employer_id,

                "isBot": False,

                "browserType": {
                    "$ne": "Unknown"
                },

                "deviceType": {
                    "$ne": "Unknown"
                },

                "isFromGoogle": True,

                "createdDt": {
                    "$gte": yesterday,
                    "$lt": today
                }
            }
        },

        {
            "$group": {
                "_id": {
                    "ip": "$ipAddress",
                    "job": "$jobId"
                }
            }
        },

        {
            "$count": "count"
        }
    ]

    clicks_result = list(
        analytics.aggregate(
            clicks_pipeline,
            allowDiskUse=True
        )
    )

    db_clicks = (
        clicks_result[0]["count"]
        if clicks_result else 0
    )

    # =====================================================
    # BOT VISITS
    # =====================================================

    bot_visits = analytics.count_documents({

        "employerId": employer_id,

        "isBot": True,

        "createdDt": {
            "$gte": yesterday,
            "$lt": today
        }
    })

    # =====================================================
    # TOTAL POSTED JOBS
    # =====================================================

    total_posted_jobs = jobs.count_documents({

        "employerId": employer_id,

        "status": "posted",

        "isActive": True
    })

    # =====================================================
    # TOTAL EXPIRED JOBS
    # =====================================================

    total_expired_jobs = jobs.count_documents({

        "employerId": employer_id,

        "status": "removed"
    })

    # =====================================================
    # TO EXPIRE IN 5 DAYS
    # =====================================================

    to_expire_5days = jobs.count_documents({

        "employerId": employer_id,

        "status": "posted",

        "isActive": True,

        "validThrough": {
            "$lt": five_days_future
        }
    })

    return {

        "To_Post": to_post,

        "Posted_Jobs": postings,

        "posted_companies": posted_companies,

        "Updated_Jobs": updates,

        "updated_companies": updated_companies,

        "Cache_Updated_Jobs": cache_updates,

        "cache_updated_companies": cache_updated_companies,

        "Expired_Jobs": expired_jobs,

        "expired_companies": expired_companies,

        "Posted_Bot": posted_bot,

        "Expires_Bot": expires_bot,

        "FeedExpiredJobs": feed_expires,

        "DB_Clicks": db_clicks,

        "Bot_Visits": bot_visits,

        "Posting_Queue": 0,

        "Expires_Queue": 0,

        "Post_Fail": 0,

        "Expires_Fail": 0,

        "To_Expire_In_5Days": to_expire_5days,

        "Reposts": reposts,

        "Total Posted Job": total_posted_jobs,

        "Total Expired Jobs": total_expired_jobs
    }

# =========================================================
# PROCESS DOMAIN
# =========================================================

def process_domain(doc):

    try:

        domain = doc.get("Domain")

        domain_type = doc.get("DomainType")

        employer_id = doc.get("employerId", "")

        print(f"\nPROCESSING : {domain}")

        db = get_database(
            domain,
            domain_type
        )

        if db is None:

            print("DB NOT FOUND")

            return False

        cols = get_collections(
            db,
            domain_type
        )

        # =================================================
        # PROXY
        # =================================================

        if domain_type == "Proxy":

            stats = get_proxy_stats(
                cols,
                employer_id
            )

        # =================================================
        # REGULAR
        # =================================================

        else:

            stats = get_regular_stats(
                cols,
                employer_id,
                domain_type
            )

        # =================================================
        # FINAL DOC
        # =================================================

        final_doc = {

            "Date": today,

            "Domain": domain,

            "DomainType": domain_type,

            "employerId": employer_id,

            **stats
        }

        output_col.update_one(
            {
                "Domain": domain,
                "Date": today
            },
            {
                "$set": final_doc
            },
            upsert=True
        )

        print(f"DONE : {domain}")

        return True

    except Exception:

        print(traceback.format_exc())

        return False

# =========================================================
# MAIN
# =========================================================

def main():

    docs = list(
        input_col.find({})
    )

    print(f"TOTAL DOMAINS : {len(docs)}")

    success = 0

    failed = 0

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                process_domain,
                doc
            )

            for doc in docs
        ]

        for future in as_completed(futures):

            result = future.result()

            if result:

                success += 1

            else:

                failed += 1

    print("\n====================================")

    print(f"SUCCESS : {success}")

    print(f"FAILED  : {failed}")

    print("====================================")

# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()