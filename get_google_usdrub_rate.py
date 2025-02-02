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

        # Достаём курс из ячейки E8 (в CSV индексация с 0, поэтому E8 = [7][4])
        raw_value = table[7][3].replace(",", ".").replace("₽", "").strip()

        try:
            usdrub_rate = float(raw_value)
            return usdrub_rate
        except ValueError:
            print(f"Ошибка конвертации: {raw_value}")

    else:
        print("Ошибка при запросе:", response.status_code)
