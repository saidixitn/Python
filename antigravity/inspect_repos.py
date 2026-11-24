import os
import json

base_dirs = {
    "vps-automations": r"./temp_repos\vps-automations",
    "Automation": r"./temp_repos\Automation",
    "PythonProject": r"./temp_repos\PythonProjec", # check folder name
    "Job-Posting-Alerts": r"./temp_repos\Job-Posting-Alerts",
    "pm2-vps": r"./temp_repos\pm2-vps",
}

for name, path in list(base_dirs.items()):
    if not os.path.exists(path):
        # Check actual folder names in temp_repos
        actual = os.listdir(r"./temp_repos")
        print(f"Directory {path} not found. Available in temp_repos: {actual}")

report = {}
for name, path in base_dirs.items():
    if not os.path.exists(path):
        continue
    file_list = []
    for root, dirs, files in os.walk(path):
        if ".git" in dirs:
            dirs.remove(".git")
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, path)
            sz = os.path.getsize(full)
            file_list.append((rel, sz))
    report[name] = file_list

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\repo_inventory.json", "w", encoding="utf-8") as out:
    json.dump(report, out, indent=2)

for name, files in report.items():
    print(f"=== {name} ({len(files)} files) ===")
    for rel, sz in sorted(files, key=lambda x: x[0])[:30]:
        print(f"  {rel} ({sz} bytes)")
    if len(files) > 30:
        print(f"  ... and {len(files) - 30} more files")
