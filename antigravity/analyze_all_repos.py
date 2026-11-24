import os
import re
import json

repos = {
    "vps-automations": r"./temp_repos\vps-automations",
    "Automation": r"./temp_repos\Automation",
    "PythonProject": r"./temp_repos\PythonProjec",
    "Job-Posting-Alerts": r"./temp_repos\Job-Posting-Alerts",
    "pm2-vps": r"./temp_repos\pm2-vps",
    "Python": r"c:\Users\JOBIAK\Documents\Python"
}

summary = {}

for r_name, r_path in repos.items():
    summary[r_name] = {
        "workflows": [],
        "pm2_configs": [],
        "python_scripts": [],
        "databases_found": set(),
        "collections_found": set(),
        "alerts_notifications": []
    }
    for root, dirs, files in os.walk(r_path):
        # Exclude git, temp_repos from Python scan
        if ".git" in dirs:
            dirs.remove(".git")
        if r_name == "Python" and "temp_repos" in dirs:
            dirs.remove("temp_repos")
        if r_name == "Python" and ".gemini" in dirs:
            dirs.remove(".gemini")
            
        for f in files:
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, r_path)
            
            # GitHub actions
            if ".github" in rel_p and f.endswith((".yml", ".yaml")):
                with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                    summary[r_name]["workflows"].append({"path": rel_p, "content": fh.read()[:2000]})
            
            # PM2 configs
            if ("config.js" in f or "ecosystem" in f or f.endswith(".config.js") or f.endswith(".config.json")):
                with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                    summary[r_name]["pm2_configs"].append({"path": rel_p, "content": fh.read()[:2000]})
                    
            # Python scripts
            if f.endswith(".py"):
                try:
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()
                        
                        # Find DB names
                        dbs = re.findall(r'\[["\']([a-zA-Z0-9_\-]+_prod|[a-zA-Z0-9_\-]+_stage|mongo_creds|ETL_[a-zA-Z0-9_]+|daily_stats|domain_expires|proxy_stats)["\']\]', content)
                        for d in dbs:
                            summary[r_name]["databases_found"].add(d)
                            
                        # Find collections
                        cols = re.findall(r'\[["\']([a-zA-Z0-9_\-]+(?:Target_P4_Opt|userAnalytics|job|creds|input|output|oldstats|jobsGoogleSubmittedLog|aj_jp_google_logs|semrush[a-zA-Z0-9_]*))["\']\]', content)
                        for c in cols:
                            summary[r_name]["collections_found"].add(c)
                            
                        # Check alerts / emails / slack / telegram / webhooks
                        if any(k in content.lower() for k in ["smtp", "send_mail", "webhook", "slack", "alert", "telegram", "twilio"]):
                            summary[r_name]["alerts_notifications"].append({
                                "file": rel_p,
                                "has_smtp": "smtp" in content.lower() or "smtplib" in content.lower(),
                                "has_webhook": "webhook" in content.lower() or "slack" in content.lower()
                            })
                            
                        # Summarize script details
                        summary[r_name]["python_scripts"].append({
                            "file": rel_p,
                            "size": len(content),
                            "first_lines": [line.strip() for line in content.splitlines()[:15] if line.strip() and not line.strip().startswith("#")][:5]
                        })
                except Exception as e:
                    pass

# Convert sets to sorted lists for json serialization
for r_name in summary:
    summary[r_name]["databases_found"] = sorted(list(summary[r_name]["databases_found"]))
    summary[r_name]["collections_found"] = sorted(list(summary[r_name]["collections_found"]))

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\repo_analysis_summary.json", "w", encoding="utf-8") as out:
    json.dump(summary, out, indent=2)

print("Repo analysis complete.")
for r_name in summary:
    print(f"\n=== {r_name} ===")
    print(f"Workflows: {len(summary[r_name]['workflows'])}")
    print(f"PM2 configs: {len(summary[r_name]['pm2_configs'])}")
    print(f"Python scripts: {len(summary[r_name]['python_scripts'])}")
    print(f"Databases: {summary[r_name]['databases_found']}")
    print(f"Collections: {summary[r_name]['collections_found']}")
    print(f"Alert scripts: {len(summary[r_name]['alerts_notifications'])}")
