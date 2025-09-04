import requests
import csv
from io import StringIO

# ID Google Таблицы
SPREADSHEET_ID = "1jB87xWjsGfvrxdpJnNsdjlY3P4o4fDEdkdsStHELdb4"


def get_usdrub_rate():
    # Запрос к таблице в формате CSV
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"

    response = requests.get(url)
    if response.status_code == 200:
        csv_data = response.text
        reader = csv.reader(StringIO(csv_data))

        # Преобразуем CSV в список
        table = list(reader)

        # Достаём курс из ячейки D7 (в CSV индексация с 0, поэтому D7 = [6][3])
        # Это содержит курс USD/RUB
        try:
            raw_value = table[6][3].replace(",", ".").replace("₽", "").strip()
            usdrub_rate = float(raw_value)
            print(f"✅ USD/RUB rate fetched from Google Sheets: {usdrub_rate}")
            return usdrub_rate
        except (IndexError, ValueError) as e:
            print(f"❌ Ошибка получения курса USD/RUB: {e}")
            if len(table) > 6 and len(table[6]) > 3:
                print(f"   Значение в ячейке: {table[6][3]}")
            return None

    else:
        print("Ошибка при запросе:", response.status_code)
        return None
