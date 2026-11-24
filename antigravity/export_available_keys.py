import os
import pandas as pd

out_dir = r"c:\Users\JOBIAK\Documents\Python\antigravity"
artifact_dir = r"C:\Users\JOBIAK\.gemini\antigravity\brain\383797c4-425e-465b-876f-9a709dea1dc6"

# Load the find script's data or query again
from find_hcsg_matching_uniquekeys import jicn_map, pj_by_uniquekey

available_keys = []
for uk, j in jicn_map.items():
    if uk not in pj_by_uniquekey:
        available_keys.append({
            "uniqueKey": uk,
            "jobtitle": j.get("jobtitle"),
            "uncleanedLocation": j.get("uncleanedLocation"),
            "gpost": j.get("gpost"),
            "job_status": j.get("job_status")
        })

df_avail = pd.DataFrame(available_keys)
print(f"Total available to post (NOT in prod_jobiak_ai): {len(df_avail)}")
print(df_avail["jobtitle"].value_counts())

csv_avail = os.path.join(out_dir, "HCSG_Available_To_Post_UniqueKeys.csv")
csv_avail_art = os.path.join(artifact_dir, "HCSG_Available_To_Post_UniqueKeys.csv")
df_avail.to_csv(csv_avail, index=False)
df_avail.to_csv(csv_avail_art, index=False)

txt_avail = os.path.join(out_dir, "HCSG_Available_To_Post_UniqueKeys.txt")
txt_avail_art = os.path.join(artifact_dir, "HCSG_Available_To_Post_UniqueKeys.txt")
with open(txt_avail, "w", encoding="utf-8") as f:
    for uk in df_avail["uniqueKey"]:
        f.write(uk + "\n")
with open(txt_avail_art, "w", encoding="utf-8") as f:
    for uk in df_avail["uniqueKey"]:
        f.write(uk + "\n")

print("Saved available to post files.")
