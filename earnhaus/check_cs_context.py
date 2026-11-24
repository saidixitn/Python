import pandas as pd
import re

df = pd.read_csv(r'c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_missing_tags_jobs.csv')

sample_jids = ['6adf3b01b472b803804d3ba3', '6ae9cac6dab36404775f850f', '6ada13676de9da0407e32557', '6ae4a33394c75103c13c0960']

for jid in sample_jids:
    row = df[df['jobId'] == jid].iloc[0]
    desc = row['mod_desc']
    print(f"=== Job {jid} ===")
    for p in desc.split('</p>'):
        if any(c in p for c in ['Cedar Rapids', 'Reading', 'Mascoutah', 'Pass', 'TX', 'IA', 'MA', 'IL']):
            print("  Context:", p[:250])
