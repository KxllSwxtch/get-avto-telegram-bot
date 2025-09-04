import requests
import csv
from io import StringIO

# ID Google Таблицы
SPREADSHEET_ID = "1jB87xWjsGfvrxdpJnNsdjlY3P4o4fDEdkdsStHELdb4"


def get_krwrub_rate():
    # Запрос к таблице в формате CSV
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv"

    response = requests.get(url)
    if response.status_code == 200:
        csv_data = response.text
        reader = csv.reader(StringIO(csv_data))

        # Преобразуем CSV в список
        table = list(reader)

        # Достаём курс из ячейки E7 (в CSV индексация с 0, поэтому E7 = [6][4])
        # Это содержит курс KRW/RUB
        try:
            raw_value = table[6][4].replace(",", ".").replace("₽", "").strip()
            krw_rub_rate = float(raw_value)
            print(f"✅ KRW/RUB rate fetched from Google Sheets: {krw_rub_rate}")
            return krw_rub_rate
        except (IndexError, ValueError) as e:
            print(f"❌ Ошибка получения курса KRW/RUB: {e}")
            if len(table) > 6 and len(table[6]) > 4:
                print(f"   Значение в ячейке: {table[6][4]}")
            return None

    else:
        print("Ошибка при запросе:", response.status_code)
        return None
