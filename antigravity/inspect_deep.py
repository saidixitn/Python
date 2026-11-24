import os
import json

files_to_read = [
    # Job-Posting-Alerts
    (r"./temp_repos\Job-Posting-Alerts\.github\workflows\posting_alerts.yml", "Job-Posting-Alerts / posting_alerts.yml"),
    (r"./temp_repos\Job-Posting-Alerts\.github\workflows\xml.yml", "Job-Posting-Alerts / xml.yml"),
    (r"./temp_repos\Job-Posting-Alerts\Alerts\posting_alerts.py", "Job-Posting-Alerts / posting_alerts.py"),
    (r"./temp_repos\Job-Posting-Alerts\xml.py", "Job-Posting-Alerts / xml.py"),
    
    # Automation
    (r"./temp_repos\Automation\.github\workflows\daily-report.yml", "Automation / daily-report.yml"),
    (r"./temp_repos\Automation\.github\workflows\email_report.yml", "Automation / email_report.yml"),
    (r"./temp_repos\Automation\clicks_email_report.py", "Automation / clicks_email_report.py"),
    (r"./temp_repos\Automation\banana.py", "Automation / banana.py"),
    
    # pm2-vps
    (r"./temp_repos\pm2-vps\Clicks Report\clicks_report.py", "pm2-vps / clicks_report.py"),
    (r"./temp_repos\pm2-vps\Clicks Report\ecosystem.config.js", "pm2-vps / clicks_report ecosystem.config.js"),
    (r"./temp_repos\pm2-vps\Proxy\api.py", "pm2-vps / Proxy api.py"),
    (r"./temp_repos\pm2-vps\Proxy\mongo_handler.py", "pm2-vps / Proxy mongo_handler.py"),
    (r"./temp_repos\pm2-vps\Proxy\targetp4_handler.py", "pm2-vps / Proxy targetp4_handler.py"),
    (r"./temp_repos\pm2-vps\Expires\universal_expires.py", "pm2-vps / Expires universal_expires.py"),
    (r"./temp_repos\pm2-vps\bigquery\hourly_views.py", "pm2-vps / bigquery hourly_views.py"),
    (r"./temp_repos\pm2-vps\ecosystem.expiry.config.js", "pm2-vps / ecosystem.expiry.config.js"),
    (r"./temp_repos\pm2-vps\auto_git_backup.sh", "pm2-vps / auto_git_backup.sh"),
    
    # vps-automations
    (r"./temp_repos\vps-automations\dc_expires.py", "vps-automations / dc_expires.py"),
    (r"./temp_repos\vps-automations\dc_expires_mail.py", "vps-automations / dc_expires_mail.py"),
    (r"./temp_repos\vps-automations\domain_expires_new.py", "vps-automations / domain_expires_new.py"),
    (r"./temp_repos\vps-automations\backup_system\final_backup.py", "vps-automations / backup_system final_backup.py"),
    
    # PythonProject
    (r"./temp_repos\PythonProjec\Alerts\alerts_prog_dc.py", "PythonProject / alerts_prog_dc.py"),
    (r"./temp_repos\PythonProjec\Alerts\posting_alerts.py", "PythonProject / posting_alerts.py"),
    (r"./temp_repos\PythonProjec\Big Query\mongo_bigquery_export.py", "PythonProject / mongo_bigquery_export.py"),
    (r"./temp_repos\PythonProjec\Earn Haus\earnhaus_prog.py", "PythonProject / earnhaus_prog.py")
]

extracted = {}
for path, label in files_to_read:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # grab first 100 lines and some key search lines
            lines = content.splitlines()
            extracted[label] = {
                "total_lines": len(lines),
                "total_chars": len(content),
                "preview": "\n".join(lines[:120]),
            }
    else:
        extracted[label] = {"error": f"File not found: {path}"}

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\deep_file_inspection.json", "w", encoding="utf-8") as out:
    json.dump(extracted, out, indent=2)

print("Extracted preview of key files. Count:", len(extracted))
