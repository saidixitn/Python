import re
import csv
import pandas as pd
from bs4 import BeautifulSoup

state_codes = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

def clean_and_fix_description(html_str):
    if not isinstance(html_str, str) or not html_str:
        return ""
    
    modified = html_str
    
    # --- 1. TAG BALANCING & STRUCTURAL FIXES ---
    # Deduplicate strong
    modified = re.sub(r'<strong>\s*<strong>', '<strong>', modified, flags=re.I)
    modified = re.sub(r'</strong>\s*</strong>', '</strong>', modified, flags=re.I)
    
    # Fix <li><strong>...</li> missing </strong>
    def fix_li(m):
        prefix = m.group(1)
        content = m.group(2)
        suffix = m.group(3)
        if '</strong>' not in content:
            return f"{prefix}{content}</strong>{suffix}"
        return m.group(0)

    modified = re.sub(r'(<li>\s*<strong>)(.*?)(</li>)', fix_li, modified, flags=re.I | re.DOTALL)
    
    # Fix unclosed <strong> before opening <p>
    def fix_unclosed_strong_before_p(m):
        content = m.group(1)
        if '</strong>' not in content:
            return f"<p><strong>{content}</strong></p><p>"
        return m.group(0)

    modified = re.sub(r'<strong>(?!.*?</strong>)(.*?)<p>', fix_unclosed_strong_before_p, modified, flags=re.I | re.DOTALL)

    # Fix <p><strong>Heading</strong><ul> (missing </p> before <ul>)
    modified = re.sub(r'(<p>\s*<strong>.*?</strong>\s*)(<ul>)', r'\1</p>\2', modified, flags=re.I | re.DOTALL)

    # Fix <p><strong>Heading</strong><p> (missing </p> between headings)
    modified = re.sub(r'(<p>\s*<strong>.*?</strong>\s*)(<p>)', r'\1</p>\2', modified, flags=re.I | re.DOTALL)

    # Clean dangling </p></p>
    modified = re.sub(r'(</p>\s*){2,}', '</p>', modified, flags=re.I)
    
    # --- 2. REMOVE CITY, STATE & LOCATION DETAILS ---
    # Remove standalone city, state paragraphs like <p><strong>Cedar Rapids, IA</strong></p>
    modified = re.sub(rf'<p>\s*(?:<strong>)?\s*[A-Za-z\s.-]+,\s*{state_codes}\s*(?:</strong>)?\s*</p>', '', modified, flags=re.I)
    
    # Remove address paragraphs like <p>901 North Tenth Street, Mascoutah, IL 62258</p>
    modified = re.sub(rf'<p>\s*\d+\s+[A-Za-z0-9\s.,-]+,\s*[A-Za-z\s.-]+,\s*{state_codes}\s+\d{{5}}\s*</p>', '', modified, flags=re.I)
    
    # Remove "in <City>, <State>" or "in<City>, <State>" from intro phrases
    modified = re.sub(rf'\s*in\s*[A-Za-z\s.-]+?,\s*{state_codes}\b', '', modified, flags=re.I)
    
    # Remove state from license requirement:
    # e.g. "license inPA." -> "license.", "license in PA." -> "license.", "license inFL." -> "license."
    modified = re.sub(rf'license\s*(?:in\s*|in)\s*{state_codes}\.?', 'license.', modified, flags=re.I)
    modified = re.sub(r'license\s*\.', 'license.', modified, flags=re.I)
    
    # --- 3. SPACING FIXES ---
    # Spacing around verbs and phrases
    modified = re.sub(r'([a-zA-Z0-9])has an exciting opportunity', r'\1 has an exciting opportunity', modified)
    modified = re.sub(r'([a-zA-Z0-9])is seeking', r'\1 is seeking', modified)
    modified = re.sub(r'([a-zA-Z0-9])is looking', r'\1 is looking', modified)
    modified = re.sub(r'for aFull-Time', r'for a Full-Time', modified, flags=re.I)
    modified = re.sub(r'for aFull-time', r'for a Full-time', modified, flags=re.I)
    modified = re.sub(r'for aPRN', r'for a PRN', modified, flags=re.I)
    modified = re.sub(r'for aPart-Time', r'for a Part-Time', modified, flags=re.I)
    modified = re.sub(r'\baFull-Time\b', r'a Full-Time', modified)
    modified = re.sub(r'\baFull-time\b', r'a Full-time', modified)
    modified = re.sub(r'packagefor', r'package for', modified, flags=re.I)
    modified = re.sub(r'opportunityfor', r'opportunity for', modified, flags=re.I)
    modified = re.sub(r'compassionatePRN', r'compassionate PRN', modified, flags=re.I)
    modified = re.sub(r'valuescompassion', r'values compassion', modified, flags=re.I)
    modified = re.sub(r'teamof', r'team of', modified, flags=re.I)
    
    # Acronym spacing: e.g. (SLP)to -> (SLP) to, (OTA)We -> (OTA). We
    modified = re.sub(r'\(([A-Z]{2,4})\)([A-Z])', r'(\1). \2', modified)
    modified = re.sub(r'\(([A-Z]{2,4})\)(to|for|is|in|with|and)\b', r'(\1) \2', modified, flags=re.I)
    
    # Facility prefixes: "At<Word>" e.g. AtLetort -> At Letort
    modified = re.sub(r'\bAt([A-Z][a-z]+)', r'At \1', modified)
    modified = re.sub(r'\bAtSt\.', r'At St.', modified)
    
    # Missing space after period between sentences e.g. "team.At" -> "team. At"
    modified = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', modified)
    
    # Clean multiple spaces
    modified = re.sub(r' {2,}', ' ', modified)
    
    # Clean and balance DOM
    soup = BeautifulSoup(modified, 'html.parser')
    return str(soup)

csv_in = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv"
df = pd.read_csv(csv_in)
print(f"Loaded {len(df)} jobs from {csv_in}")

updated_rows = []
for idx, row in df.iterrows():
    jid = row['jobId']
    url = row['SubmittedUrl']
    org_desc = row['org_desc']
    
    mod_desc = clean_and_fix_description(org_desc)
    
    updated_rows.append({
        "jobId": jid,
        "SubmittedUrl": url,
        "org_desc": org_desc,
        "mod_desc": mod_desc
    })

paths_to_write = [
    r"C:\Users\JOBIAK\.gemini\antigravity\brain\6e0488a6-8f1e-4ae7-9214-e018b0901935\qrm_missing_tags_jobs.csv",
    r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_cleaned_jobs.csv",
    r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv"
]

for p in paths_to_write:
    try:
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["jobId", "SubmittedUrl", "org_desc", "mod_desc"])
            writer.writeheader()
            writer.writerows(updated_rows)
        print(f"Successfully saved to: {p}")
    except PermissionError:
        print(f"File locked, could not overwrite: {p}")

print("Done processing!")
