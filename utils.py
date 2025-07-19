import requests
import datetime
import locale
import math
import gc
import re

PROXY = "http://B01vby:GBno0x@45.118.250.2:8000"
RESIDENTIAL_PROXY = (
    "http://oGKgjVaIooWADkOR:O8J73QYtjYWgQj4m_country-ru@geo.iproyal.com:12321"
)
proxies = {"http": RESIDENTIAL_PROXY, "https": RESIDENTIAL_PROXY}

# Список User-Agent для запросов к calcus.ru
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


def get_random_user_agent():
    """
    Returns a random user agent from the USER_AGENTS list.
    This is useful for avoiding detection as a bot.
    """
    import random

    return random.choice(USER_AGENTS)


def generate_encar_photo_url(photo_path):
    """
    Формирует правильный URL для фотографий Encar.
    Пример результата: https://ci.encar.com/carpicture02/pic3902/39027097_006.jpg
    """

    base_url = "https://ci.encar.com"
    photo_url = f"{base_url}/{photo_path}"

    return photo_url


def get_rub_to_krw_rate():
    url = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/rub.json"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        original_rate = data["rub"]["krw"]
        adjusted_rate = original_rate * 1.03
        return adjusted_rate
    except requests.RequestException as e:
        print(f"Error fetching exchange rate: {e}")
        return None


def clean_number(value):
    """Очищает строку от пробелов и преобразует в число"""
    return int(float(value.replace(" ", "").replace(",", ".")))


def get_customs_fees(engine_volume, car_price, car_year, car_month, engine_type=1):
    """
    Запрашивает расчёт таможенных платежей с сайта calcus.ru.
    :param engine_volume: Объём двигателя (куб. см)
    :param car_price: Цена авто в вонах
    :param car_year: Год выпуска авто
    :param engine_type: Тип двигателя (1 - бензин, 2 - дизель, 3 - гибрид, 4 - электромобиль)
    :return: JSON с результатами расчёта
    """
    url = "https://calcus.ru/calculate/Customs"

    payload = {
        "owner": 1,  # Физлицо
        "age": calculate_age(car_year, car_month),  # Возрастная категория
        "engine": engine_type,  # Тип двигателя (по умолчанию 1 - бензин)
        "power": 1,  # Лошадиные силы (можно оставить 1)
        "power_unit": 1,  # Тип мощности (1 - л.с.)
        "value": int(engine_volume),  # Объём двигателя
        "price": int(car_price),  # Цена авто в KRW
        "curr": "KRW",  # Валюта
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://calcus.ru/",
        "Origin": "https://calcus.ru",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при запросе к calcus.ru: {e}")
        # Возвращаем заглушку в случае ошибки
        return {"sbor": "0", "tax": "0", "util": "0"}


# Utility function to calculate the age category
# BACKUP
# def calculate_age(year, month):
#     # Убираем ведущий ноль у месяца, если он есть
#     month = int(month.lstrip("0")) if isinstance(month, str) else int(month)

#     current_date = datetime.datetime.now()
#     car_date = datetime.datetime(year=int(year), month=month, day=1)

#     age_in_months = (
#         (current_date.year - car_date.year) * 12 + current_date.month - car_date.month
#     )

#     if age_in_months < 36:
#         return f"До 3 лет"
#     elif 36 <= age_in_months < 60:
#         return f"от 3 до 5 лет"
#     else:
#         return f"от 5 лет"


# Utility function to calculate the age category
def calculate_age(year, month):
    """
    Рассчитывает возрастную категорию автомобиля по классификации calcus.ru.

    :param year: Год выпуска автомобиля
    :param month: Месяц выпуска автомобиля
    :return: Возрастная категория ("0-3", "3-5", "5-7", "7-0")
    """
    # Убираем ведущий ноль у месяца, если он есть
    month = int(month.lstrip("0")) if isinstance(month, str) else int(month)

    current_date = datetime.datetime.now()
    car_date = datetime.datetime(year=int(year), month=month, day=1)

    age_in_months = (
        (current_date.year - car_date.year) * 12 + current_date.month - car_date.month
    )

    if age_in_months < 36:
        return "0-3"
    elif 36 <= age_in_months < 60:
        return "3-5"
    elif 60 <= age_in_months < 84:
        return "5-7"
    else:
        return "7-0"


def format_number(number):
    return locale.format_string("%d", number, grouping=True)


# Округляем объёмы ДВС
def round_engine_volume(volume):
    return math.ceil(int(volume) / 100) * 100  # Округление вверх до ближайшей сотни


# Очищение памяти
def clear_memory():
    gc.collect()


# Расчёт таможенного сбора
def calculate_customs_fee(car_price_rub):
    """
    Рассчитывает таможенный сбор в зависимости от стоимости автомобиля в рублях.
    """
    if car_price_rub <= 200000:
        return 1067
    elif car_price_rub <= 450000:
        return 2134
    elif car_price_rub <= 1200000:
        return 4269
    elif car_price_rub <= 2700000:
        return 11746
    elif car_price_rub <= 4200000:
        return 16524
    elif car_price_rub <= 5500000:
        return 21344
    elif car_price_rub <= 7000000:
        return 27540
    else:
        return 30000


# Таможенная пошлина
def calculate_customs_duty(car_price_euro, engine_volume, euro_to_rub_rate, age):
    """
    Рассчитывает таможенную пошлину для РФ в зависимости от стоимости автомобиля в евро,
    объема двигателя, курса евро к рублю и возраста автомобиля.
    """
    engine_volume = int(engine_volume)

    # Для автомобилей младше 3 лет
    if age == "до 3 лет":
        if car_price_euro <= 8500:
            duty = max(car_price_euro * 0.54, engine_volume * 2.5)
        elif car_price_euro <= 16700:
            duty = max(car_price_euro * 0.48, engine_volume * 3.5)
        elif car_price_euro <= 42300:
            duty = max(car_price_euro * 0.48, engine_volume * 5.5)
        elif car_price_euro <= 84500:
            duty = max(car_price_euro * 0.48, engine_volume * 7.5)
        elif car_price_euro <= 169000:
            duty = max(car_price_euro * 0.48, engine_volume * 15)
        else:
            duty = max(car_price_euro * 0.48, engine_volume * 20)

    # Для автомобилей от 3 до 5 лет
    elif age == "от 3 до 5 лет":
        if engine_volume <= 1000:
            duty = engine_volume * 1.5
        elif engine_volume <= 1500:
            duty = engine_volume * 1.7
        elif engine_volume <= 1800:
            duty = engine_volume * 2.5
        elif engine_volume <= 2300:
            duty = engine_volume * 2.7
        elif engine_volume <= 3000:
            duty = engine_volume * 3
        else:
            duty = engine_volume * 3.6

    # Для автомобилей старше 5 лет
    elif age == "старше 5 лет" or age == "от 5 лет":
        if engine_volume <= 1000:
            duty = engine_volume * 3
        elif engine_volume <= 1500:
            duty = engine_volume * 3.2
        elif engine_volume <= 1800:
            duty = engine_volume * 3.5
        elif engine_volume <= 2300:
            duty = engine_volume * 4.8
        elif engine_volume <= 3000:
            duty = engine_volume * 5
        else:
            duty = engine_volume * 5.7

    else:
        raise ValueError("Некорректный возраст автомобиля")

    return round(duty * euro_to_rub_rate, 2)


# Утильсбор
def calculate_recycling_fee(engine_volume, age):
    """
    Рассчитывает утилизационный сбор в России для физических лиц.

    :param engine_volume: Объём двигателя в куб. см.
    :param age: Возраст автомобиля.
    :return: Утилизационный сбор в рублях.
    """
    base_rate = 20000  # Базовая ставка для легковых авто

    # Проверяем возраст автомобиля и устанавливаем соответствующий коэффициент
    if age == "до 3 лет":
        if engine_volume <= 1000:
            coefficient = 0.17
        elif engine_volume <= 2000:
            coefficient = 0.17
        elif engine_volume <= 3000:
            coefficient = 0.17
        elif engine_volume <= 3500:
            coefficient = 107.67
        else:  # Для свыше 3500 см³
            coefficient = 137.11
    else:  # Для автомобилей старше 3 лет (от 3 до 5 лет и старше 5 лет)
        if engine_volume <= 1000:
            coefficient = 0.26
        elif engine_volume <= 2000:
            coefficient = 0.26
        elif engine_volume <= 3000:
            coefficient = 0.26
        elif engine_volume <= 3500:
            coefficient = 165.84
        else:  # Для свыше 3500 см³
            coefficient = 180.24  # Исправленный коэффициент

    # Рассчитываем утилизационный сбор
    recycling_fee = base_rate * coefficient
    return round(recycling_fee, 2)
