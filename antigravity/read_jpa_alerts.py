with open(r"./temp_repos\Job-Posting-Alerts\Alerts\posting_alerts.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print("".join(lines[300:430]))
