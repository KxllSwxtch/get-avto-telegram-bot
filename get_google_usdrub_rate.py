import requests
import csv
from io import StringIO

# ID Google Таблицы (основная копия КОРЕЯ/КИТАЙ)
SPREADSHEET_ID = "1CuUkxw8or9KOxASU1e_F5qh1Sh3Y_gJRfxcVEMxvFZ8"


def get_usdrub_rate():
    # Try Google Sheets first
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&gid=1704344245"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            csv_data = response.text
            reader = csv.reader(StringIO(csv_data))
            table = list(reader)
            # Курс USD в колонке D строки «Суток на СВХ» (8-я строка листа = индекс 7)
            raw_value = table[7][3].replace(",", ".").replace("₽", "").strip()
            if raw_value:  # Check for non-empty
                usdrub_rate = float(raw_value)
                print(f"✅ USD/RUB rate fetched from Google Sheets: {usdrub_rate}")
                return usdrub_rate
            else:
                print("⚠️ Google Sheets USD cell is empty, falling back to CBR")
    except Exception as e:
        print(f"⚠️ Google Sheets failed: {e}")

    # Fallback to CBR
    try:
        cbr_url = "https://www.cbr-xml-daily.ru/daily_json.js"
        response = requests.get(cbr_url, timeout=10)
        data = response.json()
        usdrub_rate = data["Valute"]["USD"]["Value"]
        print(f"✅ USD/RUB rate fetched from CBR fallback: {usdrub_rate}")
        return usdrub_rate
    except Exception as e:
        print(f"❌ CBR fallback also failed: {e}")
        return None
