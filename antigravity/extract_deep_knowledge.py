import os
import re
import json

def inspect_all():
    analysis = {}
    
    # 1. Job-Posting-Alerts
    jpa_dir = r"./temp_repos\Job-Posting-Alerts"
    with open(os.path.join(jpa_dir, "Alerts", "posting_alerts.py"), "r", encoding="utf-8", errors="ignore") as f:
        pa_content = f.read()
    with open(os.path.join(jpa_dir, "xml.py"), "r", encoding="utf-8", errors="ignore") as f:
        xml_content = f.read()
    
    analysis["Job-Posting-Alerts"] = {
        "posting_alerts": {
            "summary": "Hourly Telegram alerting engine for job posting drops / stalls across Programmatic, Direct Apply, and Proxy clients.",
            "telegram_env": "TELEGRAM_BOT_TOKEN",
            "db_env": "LOCAL_MONGO_URI",
            "quiet_hours": "02:30 IST to 12:30 IST (suppressed during night/morning)",
            "key_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", pa_content),
            "full_code": pa_content
        },
        "xml_monitor": {
            "summary": "XML feed monitoring script running every 30 minutes to check feed accessibility, job count drops, and alert via Telegram.",
            "key_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", xml_content),
            "full_code": xml_content
        }
    }
    
    # 2. Automation
    aut_dir = r"./temp_repos\Automation"
    with open(os.path.join(aut_dir, "clicks_email_report.py"), "r", encoding="utf-8", errors="ignore") as f:
        clicks_email = f.read()
    with open(os.path.join(aut_dir, "banana.py"), "r", encoding="utf-8", errors="ignore") as f:
        banana_aut = f.read()
        
    analysis["Automation"] = {
        "clicks_email_report": {
            "summary": "Automated daily email reports of Google clicks/views per domain, HTML formatted with styling, sent via SMTP.",
            "key_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", clicks_email),
            "full_code": clicks_email
        },
        "banana": {
            "summary": "Daily Banana revenue and unique views reconciliation with Google Sheets update and multi-tenant DB query.",
            "key_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", banana_aut),
            "full_code": banana_aut
        }
    }
    
    # 3. pm2-vps
    pm2_dir = r"./temp_repos\pm2-vps"
    # list pm2 configs
    pm2_configs = []
    for f in os.listdir(pm2_dir):
        if "config" in f or "ecosystem" in f:
            p = os.path.join(pm2_dir, f)
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                    pm2_configs.append({"file": f, "content": fh.read()})
                    
    # read Clicks Report/clicks_report.py
    with open(os.path.join(pm2_dir, "Clicks Report", "clicks_report.py"), "r", encoding="utf-8", errors="ignore") as f:
        cr_content = f.read()
    # read Proxy/
    proxy_files = {}
    proxy_path = os.path.join(pm2_dir, "Proxy")
    if os.path.exists(proxy_path):
        for pf in os.listdir(proxy_path):
            if pf.endswith(".py"):
                with open(os.path.join(proxy_path, pf), "r", encoding="utf-8", errors="ignore") as fh:
                    proxy_files[pf] = fh.read()
                    
    # read Expires/universal_expires.py
    with open(os.path.join(pm2_dir, "Expires", "universal_expires.py"), "r", encoding="utf-8", errors="ignore") as f:
        ue_content = f.read()
        
    # read bigquery/hourly_views.py
    with open(os.path.join(pm2_dir, "bigquery", "hourly_views.py"), "r", encoding="utf-8", errors="ignore") as f:
        bq_content = f.read()
        
    analysis["pm2-vps"] = {
        "pm2_ecosystems": pm2_configs,
        "clicks_report_summary": {
            "length": len(cr_content),
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", cr_content),
            "first_500": cr_content[:3000]
        },
        "proxy_architecture": {
            "files": list(proxy_files.keys()),
            "api_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", proxy_files.get("api.py", "")),
            "mongo_handler_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", proxy_files.get("mongo_handler.py", "")),
            "targetp4_handler_methods": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", proxy_files.get("targetp4_handler.py", ""))
        },
        "universal_expires": {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", ue_content),
            "first_1000": ue_content[:3000]
        },
        "bigquery_hourly": {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", bq_content),
            "first_1000": bq_content[:3000]
        }
    }
    
    # 4. vps-automations
    va_dir = r"./temp_repos\vps-automations"
    va_files = {}
    for vf in ["dc_expires.py", "dc_expires_mail.py", "domain_expires_new.py", "auto_git_backup.sh"]:
        p = os.path.join(va_dir, vf)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                va_files[vf] = fh.read()
    with open(os.path.join(va_dir, "backup_system", "final_backup.py"), "r", encoding="utf-8", errors="ignore") as f:
        va_files["final_backup.py"] = f.read()
        
    analysis["vps-automations"] = {
        "dc_expires": {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", va_files.get("dc_expires.py", "")),
            "first_1000": va_files.get("dc_expires.py", "")[:3000]
        },
        "dc_expires_mail": {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", va_files.get("dc_expires_mail.py", "")),
            "first_1000": va_files.get("dc_expires_mail.py", "")[:3000]
        },
        "domain_expires_new": {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", va_files.get("domain_expires_new.py", "")),
            "first_1000": va_files.get("domain_expires_new.py", "")[:3000]
        },
        "final_backup": {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", va_files.get("final_backup.py", "")),
            "first_1000": va_files.get("final_backup.py", "")[:3000]
        },
        "auto_git_backup": va_files.get("auto_git_backup.sh", "")
    }
    
    # 5. PythonProject
    pp_dir = r"./temp_repos\PythonProjec"
    pp_files = {}
    for pf in [
        os.path.join(pp_dir, "Alerts", "alerts_prog_dc.py"),
        os.path.join(pp_dir, "Big Query", "mongo_bigquery_export.py"),
        os.path.join(pp_dir, "Big Query", "export_ewf.py"),
        os.path.join(pp_dir, "Earn Haus", "earnhaus_prog.py"),
        os.path.join(pp_dir, "Earn Haus", "earnhaus_proxy.py"),
        os.path.join(pp_dir, "Expires", "expires.py"),
        os.path.join(pp_dir, "Expires", "paa.py")
    ]:
        if os.path.exists(pf):
            with open(pf, "r", encoding="utf-8", errors="ignore") as fh:
                pp_files[os.path.basename(pf)] = fh.read()
                
    analysis["PythonProject"] = {
        k: {
            "functions": re.findall(r"def\s+([a-zA-Z0-9_]+)\(", v),
            "first_1500": v[:3000]
        }
        for k, v in pp_files.items()
    }
    
    # Save the detailed extracted data
    with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\deep_repo_knowledge.json", "w", encoding="utf-8") as out:
        json.dump(analysis, out, indent=2)
        
    print("Deep analysis extracted and saved successfully.")

inspect_all()
