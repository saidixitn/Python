import json

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\deep_repo_knowledge.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("Job-Posting-Alerts functions:")
print("posting_alerts:", d["Job-Posting-Alerts"]["posting_alerts"]["key_methods"])
print("xml_monitor:", d["Job-Posting-Alerts"]["xml_monitor"]["key_methods"])

print("\nAutomation functions:")
print("clicks_email_report:", d["Automation"]["clicks_email_report"]["key_methods"])
print("banana:", d["Automation"]["banana"]["key_methods"])

print("\npm2-vps:")
print("clicks_report methods count:", len(d["pm2-vps"]["clicks_report_summary"]["functions"]))
print("clicks_report methods:", d["pm2-vps"]["clicks_report_summary"]["functions"][:15])
print("proxy api methods:", d["pm2-vps"]["proxy_architecture"]["api_methods"])
print("proxy mongo_handler methods:", d["pm2-vps"]["proxy_architecture"]["mongo_handler_methods"])
print("proxy targetp4_handler methods:", d["pm2-vps"]["proxy_architecture"]["targetp4_handler_methods"])
print("universal_expires methods:", d["pm2-vps"]["universal_expires"]["functions"])
print("bigquery hourly methods:", d["pm2-vps"]["bigquery_hourly"]["functions"])

print("\nvps-automations:")
print("dc_expires methods:", d["vps-automations"]["dc_expires"]["functions"])
print("dc_expires_mail methods:", d["vps-automations"]["dc_expires_mail"]["functions"])
print("domain_expires_new methods:", d["vps-automations"]["domain_expires_new"]["functions"])
print("final_backup methods:", d["vps-automations"]["final_backup"]["functions"])
