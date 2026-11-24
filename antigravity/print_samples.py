import json

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\live_schemas_and_indexes.json", "r", encoding="utf-8") as f:
    d = json.load(f)

out_lines = []
for k, v in d.items():
    out_lines.append(f"=== {k} ===")
    out_lines.append("SAMPLE DOC:")
    out_lines.append(json.dumps(v.get("sample_doc"), indent=2))
    out_lines.append("INDEX NAMES:")
    idxs = v.get("indexes") or {}
    for iname, ikey in idxs.items():
        out_lines.append(f"  - {iname}: {ikey}")
    out_lines.append("")

with open(r"c:\Users\JOBIAK\Documents\Python\antigravity\readable_schemas_indexes.txt", "w", encoding="utf-8") as out:
    out.write("\n".join(out_lines))
print("Wrote readable_schemas_indexes.txt, lines:", len(out_lines))
