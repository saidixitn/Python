import openpyxl

wb = openpyxl.load_workbook(r'C:/Users/JOBIAK/Downloads/Keywords - All Clients.xlsx', data_only=False)
ws = wb['Yes Communities']

current_title = None
sections = {}

for r in range(1, ws.max_row+1):
    c1 = ws.cell(row=r, column=1).value
    c3 = ws.cell(row=r, column=3).value
    c5 = ws.cell(row=r, column=5).value
    c7 = ws.cell(row=r, column=7).value
    c8 = ws.cell(row=r, column=8).value
    c9 = ws.cell(row=r, column=9).value

    if c1 and (c3 == 'Location Keywords' or (r > 20 and not c3 and 'Agent' in str(c1))):
        current_title = str(c1).strip()
        if current_title not in sections:
            sections[current_title] = {'location': [], 'company': [], 'title': []}
    
    if current_title:
        if c3 and c3 != 'Location Keywords':
            sections[current_title]['location'].append(str(c3).strip())
        if c5 and c5 != 'Company Keywords':
            sections[current_title]['company'].append(str(c5).strip())
        if c7 and c7 != 'Title-to-Title Keywords':
            sections[current_title]['title'].append(str(c7).strip())
        if c8:
            sections[current_title]['title'].append(str(c8).strip())
        if c9:
            sections[current_title]['title'].append(str(c9).strip())

print(f"Total titles parsed: {len(sections)}")
for title, data in sections.items():
    print(f"\nTitle: {title}")
    print(f"  Location keywords ({len(data['location'])}): {data['location']}")
    print(f"  Company keywords ({len(data['company'])}): {data['company']}")
    print(f"  Title keywords ({len(data['title'])}): {data['title']}")
