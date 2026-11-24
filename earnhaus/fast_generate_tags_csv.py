import re
import csv
import pandas as pd
from bs4 import BeautifulSoup

source_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_description_fixes.csv"
print(f"Reading {source_csv}...")
df = pd.read_csv(source_csv)
print(f"Total rows in source: {len(df)}")

def fix_missing_tags(html_str):
    if not isinstance(html_str, str) or not html_str:
        return ""
    
    # 1. Clean up duplicated <strong><strong> tags
    fixed = re.sub(r'<strong>\s*<strong>', '<strong>', html_str, flags=re.I)
    fixed = re.sub(r'</strong>\s*</strong>', '</strong>', fixed, flags=re.I)
    
    # 2. Fix <li><strong>text</li> where </strong> is missing before </li>
    def fix_li(m):
        prefix = m.group(1)
        content = m.group(2)
        suffix = m.group(3)
        if '</strong>' not in content:
            return f"{prefix}{content}</strong>{suffix}"
        return m.group(0)

    fixed = re.sub(r'(<li>\s*<strong>)(.*?)(</li>)', fix_li, fixed, flags=re.I | re.DOTALL)
    
    # 3. Fix unclosed <strong> before opening <p> (e.g., </p><strong>intro...<p>)
    def fix_unclosed_strong_before_p(m):
        content = m.group(1)
        if '</strong>' not in content:
            return f"<p><strong>{content}</strong></p><p>"
        return m.group(0)

    fixed = re.sub(r'<strong>(?!.*?</strong>)(.*?)<p>', fix_unclosed_strong_before_p, fixed, flags=re.I | re.DOTALL)

    # 4. Fix <p><strong>Heading</strong><ul> (missing </p> before <ul>)
    fixed = re.sub(r'(<p>\s*<strong>.*?</strong>\s*)(<ul>)', r'\1</p>\2', fixed, flags=re.I | re.DOTALL)

    # 5. Fix <p><strong>Heading</strong><p> (missing </p> between headings)
    fixed = re.sub(r'(<p>\s*<strong>.*?</strong>\s*)(<p>)', r'\1</p>\2', fixed, flags=re.I | re.DOTALL)

    # 6. Clean dangling </p></p>
    fixed = re.sub(r'(</p>\s*){2,}', '</p>', fixed, flags=re.I)

    # 7. Use BeautifulSoup to balance all remaining unbalanced tags cleanly
    soup = BeautifulSoup(fixed, 'html.parser')
    clean_html = str(soup)
    
    return clean_html

issue_records = []

for idx, row in df.iterrows():
    jid = str(row.get("jobId", ""))
    url = str(row.get("SubmittedUrl", ""))
    org_desc = str(row.get("org_desc", "")) if pd.notna(row.get("org_desc")) else ""
    
    if not org_desc:
        continue

    s_open = len(re.findall(r'<strong\b[^>]*>', org_desc, re.I))
    s_close = len(re.findall(r'</strong\s*>', org_desc, re.I))
    
    p_open = len(re.findall(r'<p\b[^>]*>', org_desc, re.I))
    p_close = len(re.findall(r'</p\s*>', org_desc, re.I))
    
    has_doubled_strong = bool(re.search(r'<strong>\s*<strong>', org_desc, re.I))
    unclosed_li_strong = bool(re.search(r'<li>\s*<strong>(?!.*?</strong>).*?</li>', org_desc, re.I | re.DOTALL))
    unclosed_strong_before_p = bool(re.search(r'<strong>(?!.*?</strong>).*?<p>', org_desc, re.I | re.DOTALL))
    missing_p_close_before_ul = bool(re.search(r'<p>\s*<strong>.*?</strong>\s*<ul>', org_desc, re.I | re.DOTALL))
    dangling_p_close = bool(re.search(r'</p>\s*</p>', org_desc, re.I))
    
    has_tag_issue = (
        (s_open != s_close) or 
        has_doubled_strong or 
        unclosed_li_strong or 
        unclosed_strong_before_p or 
        (p_open != p_close) or 
        missing_p_close_before_ul or 
        dangling_p_close
    )
    
    if has_tag_issue:
        mod_desc = fix_missing_tags(org_desc)
        issue_records.append({
            "jobId": jid,
            "SubmittedUrl": url,
            "org_desc": org_desc,
            "mod_desc": mod_desc
        })

print(f"Total jobs with missing/malformed HTML tags: {len(issue_records)}")

artifact_csv = r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_missing_tags_jobs.csv"
local_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv"

for csv_path in [artifact_csv, local_csv]:
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["jobId", "SubmittedUrl", "org_desc", "mod_desc"])
        writer.writeheader()
        writer.writerows(issue_records)

print(f"Successfully saved {len(issue_records)} records to CSV files!")
