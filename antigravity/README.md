# Antigravity Workspace Directory

This folder is reserved for all new operational scripts, utilities, and architectural references to keep the root directory clean and uncluttered.

## Contents

- [`SYSTEM_KNOWLEDGE_BASE.md`](file:///c:/Users/JOBIAK/Documents/Python/antigravity/SYSTEM_KNOWLEDGE_BASE.md): Full technical reference detailing all databases, collections, field dictionaries, proxy vs direct apply vs programmatic logic, keyword schemas, bot filtering, and existing scripts.
- [`db_helper.py`](file:///c:/Users/JOBIAK/Documents/Python/antigravity/db_helper.py): Reusable thread-safe database connection module that automatically queries `mongo_creds.creds` to resolve connections to `prod_jobiak_ai`, `directclients_prod`, `ETL_Scrapping_Data`, `data_cleansing`, etc.

## Quick Usage in New Scripts

```python
import sys
import os

# Allow imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from antigravity.db_helper import get_database_by_name

# Resolve any database dynamically
db = get_database_by_name("directclients_prod")
jobs = db["Target_P4_Opt"]
```
