import datetime
import locale
import math
import gc


# Utility function to calculate the age category
def calculate_age(year, month):
    # Убираем ведущий ноль у месяца, если он есть
    month = int(month.lstrip("0")) if isinstance(month, str) else int(month)

    current_date = datetime.datetime.now()
    car_date = datetime.datetime(year=int(year), month=month, day=1)

    age_in_months = (
        (current_date.year - car_date.year) * 12 + current_date.month - car_date.month
    )

    if age_in_months < 36:
        return f"До 3 лет"
    elif 36 <= age_in_months < 60:
        return f"от 3 до 5 лет"
    else:
        return f"от 5 лет"


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
            coefficient = 89.73
        else:
            coefficient = 114.26
    else:  # Для автомобилей старше 3 лет
        if engine_volume <= 1000:
            coefficient = 0.26
        elif engine_volume <= 2000:
            coefficient = 0.26
        elif engine_volume <= 3000:
            coefficient = 0.26
        elif engine_volume <= 3500:
            coefficient = 137.36
        else:
            coefficient = 150.2

    # Рассчитываем утилизационный сбор
    recycling_fee = base_rate * coefficient
    return round(recycling_fee, 2)
