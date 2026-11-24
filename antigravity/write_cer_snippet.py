with open(r"./temp_repos\Automation\clicks_email_report.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\cer_snippet.txt", "w", encoding="utf-8") as out:
    out.write("".join(lines[:120]))
