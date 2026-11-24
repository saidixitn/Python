import pandas as pd
import re

df = pd.read_csv(r'c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv')

for idx, row in df.head(10).iterrows():
    desc = row['mod_desc']
    jid = row['jobId']
    print(f"=== Job: {jid} ===")
    
    # Check "license in"
    lic = re.findall(r'license in\s*[A-Za-z]{2,}', desc, re.I)
    if lic:
        print("  License:", lic)
        
    # Check city, state patterns
    cs = re.findall(r'\b[A-Z][a-zA-Z\s]{2,15},\s*[A-Z]{2}\b', desc)
    if cs:
        print("  City, State:", [x for x in cs if "Management" not in x and "Rehab" not in x])
        
    # Check intro paragraph
    p_tags = re.findall(r'<p>(.*?)</p>', desc, re.DOTALL)
    for p in p_tags[:3]:
        print("  P-tag:", p[:100])
