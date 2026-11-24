import csv

for name, path in [
    ("CSV 1 (jobiak_keyword_Updation)", r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_New_Keywords_All_14col.csv"),
    ("CSV 2 (rula_location_keywords)", r"c:\Users\JOBIAK\Documents\Python\antigravity\YES_Communities_New_Keywords_Location_10col.csv")
]:
    with open(path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        header = reader[0]
        data = reader[1:]
        print(f"=== {name} ===")
        print(f"Header ({len(header)} cols): {header}")
        print(f"Data Rows: {len(data)}")
        
        title_idx = header.index("title")
        kt_idx = header.index("keywordType")
        emp_idx = header.index("employerId")
        comp_idx = header.index("companyName")
        
        breakdown = {}
        for row in data:
            t = row[title_idx]
            kt = row[kt_idx]
            breakdown.setdefault(t, {})
            breakdown[t][kt] = breakdown[t].get(kt, 0) + 1
            if t != t.lower():
                print(f"  WARNING: Non-lowercase title: {t}")
            if row[emp_idx] != "6a86c3d7060e8f0b78b0dc66":
                print(f"  WARNING: Incorrect employerId: {row[emp_idx]}")
            if row[comp_idx] != "yes! communities":
                print(f"  WARNING: Incorrect companyName: {row[comp_idx]}")

        for t, kts in sorted(breakdown.items()):
            print(f"  {t:36s} -> {kts}")
        print()
