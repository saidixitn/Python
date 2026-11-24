import pandas as pd
import re
from bs4 import BeautifulSoup

source_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_description_fixes.csv"
df = pd.read_csv(source_csv)

issue_ids = [
    "6adf3d332056e50380a450cc",
    "6adc9709e376156cb260f4fe",
    "6adc96256de9da0407e345d4",
    "6adf3cdd44ab7804720b513c"
]

state_codes = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

def clean_and_fix_description(html_str):
    if not isinstance(html_str, str) or not html_str:
        return ""
    
    modified = html_str
    
    # --- 1. TAG BALANCING & STRUCTURAL FIXES ---
    # Fix <li><strong>...</li> missing </strong>
    def fix_li(m):
        prefix = m.group(1)
        content = m.group(2)
        suffix = m.group(3)
        if '</strong>' not in content:
            return f"{prefix}{content}</strong>{suffix}"
        return m.group(0)

    modified = re.sub(r'(<li>\s*<strong>)(.*?)(</li>)', fix_li, modified, flags=re.I | re.DOTALL)
    
    # Deduplicate strong
    modified = re.sub(r'<strong>\s*<strong>', '<strong>', modified, flags=re.I)
    modified = re.sub(r'</strong>\s*</strong>', '</strong>', modified, flags=re.I)

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
    modified = re.sub(rf'license\s*(?:in\s*|in)\s*{state_codes}\.?', 'license.', modified, flags=re.I)
    modified = re.sub(r'license\s*\.', 'license.', modified, flags=re.I)
    
    # --- 3. SPACING FIXES ---
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
    
    modified = re.sub(r'\(([A-Z]{2,4})\)([A-Z])', r'(\1). \2', modified)
    modified = re.sub(r'\(([A-Z]{2,4})\)(to|for|is|in|with|and)\b', r'(\1) \2', modified, flags=re.I)
    
    modified = re.sub(r'\bAt([A-Z][a-z]+)', r'At \1', modified)
    modified = re.sub(r'\bAtSt\.', r'At St.', modified)
    
    modified = re.sub(r'([a-z])\.([A-Z])', r'\1. \2', modified)
    
    modified = re.sub(r' {2,}', ' ', modified)
    
    soup = BeautifulSoup(modified, 'html.parser')
    return str(soup)

for jid in issue_ids:
    row = df[df['jobId'] == jid].iloc[0]
    org = row['org_desc']
    mod = clean_and_fix_description(org)
    
    s_open = len(re.findall(r'<strong\b[^>]*>', mod, re.I))
    s_close = len(re.findall(r'</strong\s*>', mod, re.I))
    
    print(f"JobId: {jid}")
    print(f"  Org tags: <strong={len(re.findall(r'<strong', org, re.I))}, </strong={len(re.findall(r'</strong', org, re.I))}")
    print(f"  Mod tags: <strong={s_open}, </strong={s_close} (Mismatch: {s_open != s_close})")
    # Check if city/state left in intro
    print(f"  Intro: {mod[:200]}")
    # Check license
    for p in mod.split('</li>'):
        if 'license' in p.lower():
            print(f"  License: {p}")
    print("-" * 50)
