#!/usr/bin/env python3
"""
Orchestrator script for Daily Proxy Updates and Proxy Expires.
Runs sequentially:
  1. updates.py (Root Active Update Eligibility)
  2. expires.py (Root Feed-to-Prod Reconciliation)
"""

import sys
import os
import subprocess
import logging
from datetime import datetime

# Setup workspace and logging
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORKSPACE)
os.chdir(WORKSPACE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | [DailyRunner] %(message)s",
)
logger = logging.getLogger("ProxyDailyRunner")


def run_script(script_name: str) -> bool:
    script_path = os.path.join(WORKSPACE, script_name)
    logger.info("=" * 65)
    logger.info("STARTING: %s at %s", script_name, datetime.now())
    logger.info("=" * 65)

    python_bin = sys.executable

    result = subprocess.run(
        [python_bin, script_path],
        cwd=WORKSPACE,
    )

    if result.returncode == 0:
        logger.info("SUCCESS: %s completed successfully.", script_name)
        return True
    else:
        logger.error("FAILURE: %s failed with exit code %s", script_name, result.returncode)
        return False


def main():
    start_time = datetime.now()
    logger.info("=================================================================")
    logger.info("DAILY PROXY PIPELINE STARTED at %s", start_time)
    logger.info("Step 1: updates.py | Step 2: expires.py")
    logger.info("=================================================================")

    # Step 1: Run updates.py
    logger.info(">>> Step 1/2: Executing updates.py...")
    updates_ok = run_script("updates.py")

    # Step 2: Run expires.py
    logger.info(">>> Step 2/2: Executing expires.py...")
    expires_ok = run_script("expires.py")

    end_time = datetime.now()
    duration = end_time - start_time
    logger.info("=================================================================")
    logger.info("DAILY PROXY PIPELINE COMPLETED in %s", duration)
    logger.info("updates.py status: %s", "SUCCESS" if updates_ok else "FAILED")
    logger.info("expires.py status: %s", "SUCCESS" if expires_ok else "FAILED")
    logger.info("=================================================================")

    if not updates_ok or not expires_ok:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
