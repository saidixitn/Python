import gspread

def test_sheet():
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key("1unl4wc1P7JE51xCOCtUxXjj5ZjM4VWQKbWn0p1F-Sds")
    sheet_title = "Dixit"
    try:
        ws = sh.worksheet(sheet_title)
        print(f"Worksheet '{sheet_title}' already exists.")
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_title, rows=500, cols=30)
        print(f"Created worksheet '{sheet_title}'.")

if __name__ == "__main__":
    test_sheet()
