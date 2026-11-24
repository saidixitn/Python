import pandas as pd
import re

df = pd.read_csv(r'c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv')

state_codes = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

patterns_found = {}

for idx, row in df.iterrows():
    desc = row['mod_desc']
    
    # 1. license in <State>
    m1 = re.findall(rf'license\s*(?:in\s*|in)({state_codes})\b', desc, re.I)
    if m1:
        patterns_found['license_in_state'] = patterns_found.get('license_in_state', 0) + len(m1)
        
    # 2. City, State: e.g. "Athens, TX" or "Wayland, MA"
    m2 = re.findall(rf'\b([A-Z][a-zA-Z\s.-]+?),\s*({state_codes})\b', desc)
    for c, s in m2:
        c_clean = c.strip()
        if c_clean not in ["Rehab Management", "Management", "LLC"]:
            key = f"City, State: {c_clean}, {s}"
            patterns_found[key] = patterns_found.get(key, 0) + 1

print("Top patterns found:")
for k, v in sorted(patterns_found.items(), key=lambda x: x[1], reverse=True)[:30]:
    print(f"  {k}: {v}")
