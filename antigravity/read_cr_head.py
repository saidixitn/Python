with open(r"./temp_repos\pm2-vps\Clicks Report\clicks_report.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print("".join(lines[:120]))
