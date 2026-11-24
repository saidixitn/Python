import pandas as pd
from bs4 import BeautifulSoup
import difflib

df = pd.read_csv(r"c:\Users\JOBIAK\Documents\Python\earnhaus\qrm_posted_jobs_description_fixes.csv")

bad_row = df[df['jobId'] == '6adf3a1192132b036d3e9b8d'].iloc[0]
fine_row = df[df['jobId'] == '6adda5d548a2ed0358c4cea9'].iloc[0]

bad_desc = bad_row['org_desc']
fine_desc = fine_row['org_desc']

print("=== FINE JOB HTML ===")
print(fine_desc[:800])
print("\n... middle ...\n")
print(fine_desc[800:1600])

print("\n=== BAD JOB HTML ===")
print(bad_desc[:800])
print("\n... middle ...\n")
print(bad_desc[800:1600])
