import re

with open(r"./temp_repos\pm2-vps\Clicks Report\clicks_report.py", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

classes = re.findall(r"class\s+([a-zA-Z0-9_]+)", text)
comments = re.findall(r"^(?:#|=|-)+\s*([A-Z0-9\s\-_/]+)\s*(?:#|=|-)+$", text, flags=re.MULTILINE)
print("Classes:", classes)
print("Major Section Headers:", [c.strip() for c in comments if len(c.strip()) > 3][:30])

# Let's inspect the main logic and what databases/collections it reads
dbs = set(re.findall(r'\[["\']([a-zA-Z0-9_\-]+)["\']\]', text))
print("\nDirect indexed names (approx):", [d for d in dbs if any(k in d for k in ["stats", "creds", "prod", "Target", "job", "analytics", "output", "input"])])
