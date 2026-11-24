# Python Operations Scripts

Collection of PM2-scheduled scripts for job-board analytics, Google Sheets sync, proxy exports, revenue reporting, and GenAI FAQ generation.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Place `credentials.json` and `.env` in the project root. Both are gitignored.

## Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `MONGO_URI` | Most scripts | Root MongoDB connection for creds lookup |
| `SEMRUSH_MONGO_URI` | `Stats/semrush_urls.py`, `Stats/expires.py` | Semrush whitelist database |
| `JFR_MONGO_URI` | `GenAI/jobforrep.py` | JobForRep Mongo connection |
| `SMTP_PASS` | Email scripts | Gmail app password |
| `SMTP_USER` | `Stats/stats_email.py` | Gmail sender (default: your-email@example.com) |
| `SMTP_SENDER` | `Proxy/updates_postings.py` | Export email sender |
| `SMTP_RECEIVER` | `Proxy/updates_postings.py` | Export email recipient |
| `SMTP_CC` | `Proxy/updates_postings.py` | Export email CC |
| `GOOGLE_CREDENTIALS` | Sheets scripts | Path to service account JSON |
| `GOOGLE_APPLICATION_CREDENTIALS` | `Revenue/banana.py`, `Stats/bigquery_sync.py` | Google credentials path |
| `PROJECT_ID` | `Stats/bigquery_sync.py` | BigQuery project ID |
| `IS_REMOTE_API_URL` | `Stats/to_post.py` | isRemote update API endpoint |
| `DOMAIN_API_MAP` | `Stats/to_post.py` | Optional JSON map of `domain_prod` → public domain |

## Scripts

### Stats/

Comprehensive architecture guide, calculations, and data dictionary: see [Stats/README.md](Stats/README.md).

| Script | Purpose |
|--------|---------|
| `dailystats.py` | Daily domain stats pipeline (Today snapshot + Yesterday closed window) → `daily_stats.output` |
| `dailystats_old.py` | Historical cumulative backfill engine (2026-08-01 to 2026-11-05) → `daily_stats.oldstats` |
| `stats.py` | Daily domain stats from MongoDB → `daily_stats.output` |
| `clicks_report.py` | Unique IP clicks analysis & IP grouping report |
| `to_post.py` | Jobs to post → Google Sheet "Postings" |
| `semrush_urls.py` | Semrush URL view_exists audit |
| `expires.py` | Zero-view job expiry candidates |
| `stats_email.py` | Daily clicks HTML email report |
| `bigquery_sync.py` | Google Sheets → BigQuery sync |

### Revenue/

| Script | Purpose |
|--------|---------|
| `banana.py` | Unique IP clicks report → Mongo + Google Sheet |
| `creds.py` | Mongo URI health check and cred sync |
| `whatjobs.py` | WhatJobs revenue sheet sync |
| `jobget.py` | JobGet revenue sheet sync |

### Proxy/

| Script | Purpose |
|--------|---------|
| `updates_postings.py` | Proxy Postings/Updates CSV export + email |

### GenAI/

| Script | Purpose |
|--------|---------|
| `test_ai.py` | FAQ worker via OpenRouter + proxies |
| `test.py` | Simpler OpenRouter FAQ worker |
| `jobforrep.py` | One-off job sampling |

## PM2

Configs live in `pm2/`. Start from the project root:

```bash
pm2 start pm2/banana.config.js
pm2 start pm2/to_post.config.js
pm2 start pm2/stats_email.config.js
pm2 start pm2/semrush.config.js
pm2 start pm2/proxy.config.js
pm2 start pm2/creds.config.js
pm2 start pm2/bigquery.config.js
```

Logs are written to `pm2/logs/`.

### Manual runs

```bash
# Revenue report (defaults to yesterday)
python Revenue/banana.py
python Revenue/banana.py 2026-05-21

# Clicks email (defaults to yesterday)
python Stats/stats_email.py
python Stats/stats_email.py 2026-05-21

# Daily stats (operational run)
python Stats/dailystats.py

# Historical backfill
python Stats/dailystats_old.py
```

### Launchers

- `run_report.ps1` — PowerShell launcher for banana report
- `run_report.sh` — Bash launcher for banana report (Git Bash / WSL)

## Utilities

- `fix_pm2.py` — Reset stuck PM2 daemon (requires Administrator on Windows)
