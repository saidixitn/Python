import pandas as pd
import re

source_csv = r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_description_fixes.csv"
df = pd.read_csv(source_csv)

fine_ids = [
    "6adda5d548a2ed0358c4cea9",
    "6ae9cc41673a5103d5021031",
    "6ae4a6c0b472b803804d7b5c",
    "6ae0a5995b89f003f208eafa",
    "6ae1d9eb855f8c0394f3822f"
]

issue_ids = [
    "6adf3a1192132b036d3e9b8d",
    "6adf3d332056e50380a450cc",
    "6adc9709e376156cb260f4fe",
    "6adc96256de9da0407e345d4",
    "6adf3cdd44ab7804720b513c"
]

def has_strong_issue(desc):
    if not isinstance(desc, str):
        return False
    s_open = len(re.findall(r'<strong\b[^>]*>', desc, re.I))
    s_close = len(re.findall(r'</strong\s*>', desc, re.I))
    return s_open > s_close

print("Verifying Fine Jobs:")
for jid in fine_ids:
    row = df[df['jobId'] == jid]
    if len(row) > 0:
        d = row.iloc[0]['org_desc']
        print(f"  {jid}: has_issue = {has_strong_issue(d)} (open={len(re.findall(r'<strong', d, re.I))}, close={len(re.findall(r'</strong', d, re.I))})")

print("\nVerifying Issue Jobs:")
for jid in issue_ids:
    row = df[df['jobId'] == jid]
    if len(row) > 0:
        d = row.iloc[0]['org_desc']
        print(f"  {jid}: has_issue = {has_strong_issue(d)} (open={len(re.findall(r'<strong', d, re.I))}, close={len(re.findall(r'</strong', d, re.I))})")

total_issue_jobs = 0
for idx, row in df.iterrows():
    if has_strong_issue(row.get('org_desc', '')):
        total_issue_jobs += 1

print(f"\nTotal jobs in dataset with unclosed strong tags: {total_issue_jobs}")
