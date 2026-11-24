with open(r"./temp_repos\Job-Posting-Alerts\Alerts\posting_alerts.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\jpa_alerts_snippet.txt", "w", encoding="utf-8") as out:
    out.write("".join(lines[300:430]))

print("Wrote snippet cleanly.")
