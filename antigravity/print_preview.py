import json

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\deep_file_inspection.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for label, info in data.items():
    print(f"==================================================")
    print(f"FILE: {label} (Lines: {info.get('total_lines')}, Size: {info.get('total_chars')})")
    print(f"==================================================")
    print(info.get("preview", "")[:1500])
    print("\n")
