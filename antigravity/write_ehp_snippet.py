with open(r"./temp_repos\PythonProjec\Earn Haus\earnhaus_prog.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\ehp_snippet.txt", "w", encoding="utf-8") as out:
    out.write("".join(lines[:100]))
