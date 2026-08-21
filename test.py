import gspread

gc = gspread.service_account(filename="borderliner-credentials.json")
sh = gc.open_by_key("1a6fCFKO2y6r04Z2U8N495nzN1S9-SEas_21ldnqFBcY")
ws = sh.get_worksheet(0)
ws.append_row(["test"])
print("OK")