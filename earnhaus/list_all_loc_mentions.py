import pandas as pd
import re
from bs4 import BeautifulSoup

df = pd.read_csv(r'c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv')

state_codes = r'(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)'

locations_found = []

for idx, row in df.iterrows():
    jid = row['jobId']
    desc = row['mod_desc']
    soup = BeautifulSoup(desc, 'html.parser')
    
    # Check paragraphs that look like locations or addresses
    for p in soup.find_all(['p', 'strong']):
        txt = p.get_text().strip()
        # Check standalone city, state
        if re.match(rf'^[A-Za-z\s.-]+,\s*{state_codes}$', txt):
            locations_found.append((jid, 'standalone_city_state', txt))
        # Check address with zip
        elif re.search(rf'\b\d+\s+[A-Za-z0-9\s.-]+,\s*[A-Za-z\s.-]+,\s*{state_codes}\s+\d{{5}}\b', txt):
            locations_found.append((jid, 'full_address', txt))
        # Check "in <City>, <State>"
        elif re.search(rf'in\s*[A-Za-z\s.-]+,\s*{state_codes}\b', txt):
            locations_found.append((jid, 'in_city_state', txt))

print(f"Total location mentions found in paragraphs: {len(locations_found)}")
for loc in locations_found[:30]:
    print(loc)
