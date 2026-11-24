with open(r"./temp_repos\PythonProjec\Big Query\mongo_bigquery_export.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\mbq_snippet.txt", "w", encoding="utf-8") as out:
    out.write("".join(lines[:100]))
