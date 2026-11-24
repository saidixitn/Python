import pandas as pd
import re

df = pd.read_csv(r'c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv')

state_codes = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

# Check license in <State>
lic_matches = []
# Check City, State matches
cs_matches = []
# Check "in <City>, <State>" or "in <City>"
in_city_matches = []

for idx, row in df.iterrows():
    desc = row['mod_desc']
    jid = row['jobId']
    
    # license
    for m in re.finditer(rf'(license\s*(?:in\s*|in)\s*({state_codes})\b\.?)', desc, re.I):
        lic_matches.append((jid, m.group(0), m.group(2)))
        
    # city, state
    for m in re.finditer(rf'\b([A-Z][a-zA-Z\s.-]+?),\s*({state_codes})\b', desc):
        c, s = m.group(1).strip(), m.group(2)
        if c not in ["Rehab Management", "Management", "LLC"]:
            cs_matches.append((jid, m.group(0), c, s))

print(f"Total license with state occurrences: {len(lic_matches)}")
if lic_matches:
    print("Sample license matches:", lic_matches[:5])
    
print(f"Total City, State occurrences: {len(cs_matches)}")
if cs_matches:
    print("Sample City, State matches:", cs_matches[:15])
