import requests
import csv
from io import StringIO

# ID Google Таблицы с расходами по России
SPREADSHEET_ID = "1jB87xWjsGfvrxdpJnNsdjlY3P4o4fDEdkdsStHELdb4"

# Fallback defaults
DEFAULT_FEES = {
    "broker_rub": 17146,
    "svh_rub": 35000,
    "lab_rub": 20000,
    "perm_registration_rub": 8000,
}


def _parse_rub_value(raw):
    """Parse a RUB value like '35 000 ₽' into a float."""
    cleaned = raw.replace("\u00a0", "").replace(" ", "").replace("₽", "").replace(",", ".").strip()
    return float(cleaned)


def get_russia_fees():
    """Fetch Russia fees from Google Sheet.

    Returns dict with keys: broker_rub, svh_rub, lab_rub, perm_registration_rub.
    Falls back to hardcoded defaults on failure.
    """
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&gid=1704344245"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            csv_data = response.text
            reader = csv.reader(StringIO(csv_data))
            table = list(reader)

            broker_rub = _parse_rub_value(table[22][5])
            svh_rub = _parse_rub_value(table[23][5])
            lab_rub = _parse_rub_value(table[24][5])
            perm_registration_rub = _parse_rub_value(table[25][5])

            fees = {
                "broker_rub": broker_rub,
                "svh_rub": svh_rub,
                "lab_rub": lab_rub,
                "perm_registration_rub": perm_registration_rub,
            }
            print(f"✅ Russia fees fetched from Google Sheets: {fees}")
            return fees
        else:
            print(f"⚠️ Google Sheets returned status {response.status_code}, using defaults")
    except Exception as e:
        print(f"⚠️ Google Sheets fees fetch failed: {e}, using defaults")

    print(f"ℹ️ Using default Russia fees: {DEFAULT_FEES}")
    return dict(DEFAULT_FEES)
