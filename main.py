import telebot
import psycopg2
import os
import re
import requests
import locale
import datetime
import logging
import urllib.parse

from telebot import types
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
from utils import (
    calculate_customs_fee,
    clear_memory,
    calculate_customs_duty,
    calculate_recycling_fee,
    round_engine_volume,
    calculate_age,
    format_number,
    get_customs_fees,
    clean_number,
)

CALCULATE_CAR_TEXT = "Расчёт по ссылке с Encar"
MANUAL_CAR_TEXT = "Расчёт стоимости вручную"
DEALER_COMMISSION = 0.00  # 2%


# Настройка БД
DATABASE_URL = "postgres://uea5qru3fhjlj:p44343a46d4f1882a5ba2413935c9b9f0c284e6e759a34cf9569444d16832d4fe@c97r84s7psuajm.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com:5432/d9pr93olpfl9bj"


# Configure logging
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Load keys from .env file
load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot("7759263308:AAGNbWbjop76z9GKUMfannPWzjxOFGu-QGo")

# Set locale for number formatting
locale.setlocale(locale.LC_ALL, "en_US.UTF-8")

# Storage for the last error message ID
last_error_message_id = {}

# global variables
car_data = {}
user_manual_input = {}
car_id_external = ""
total_car_price = 0
users = set()
admins = [7311593407, 728438182]
car_month = None
car_year = None

usd_rate = 0
krw_rub_rate = None
eur_rub_rate = None

vehicle_id = None
vehicle_no = None


def print_message(message):
    print("\n\n##############")
    print(f"{message}")
    print("##############\n\n")
    return None


# Функция для установки команд меню
def set_bot_commands():
    commands = [
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("cbr", "Курсы валют"),
        # types.BotCommand("stats", "Статистика"),
    ]
    bot.set_my_commands(commands)


# Функция для получения курсов валют с API
def get_currency_rates():
    global usd_rate, krw_rub_rate, eur_rub_rate

    print_message("ПОЛУЧАЕМ КУРС ЦБ")

    url = "https://www.cbr-xml-daily.ru/daily_json.js"
    response = requests.get(url)
    data = response.json()

    eur = data["Valute"]["EUR"]["Value"] + (
        data["Valute"]["EUR"]["Value"] * DEALER_COMMISSION
    )
    usd = data["Valute"]["USD"]["Value"] + (
        data["Valute"]["USD"]["Value"] * DEALER_COMMISSION
    )
    krw = (
        data["Valute"]["KRW"]["Value"]
        + (data["Valute"]["KRW"]["Value"] * DEALER_COMMISSION)
    ) / data["Valute"]["KRW"]["Nominal"]

    usd_rate = usd

    # Добавляем 3% к курсу воны к рублю (как в HTML-калькуляторе)
    krw = round(krw, 3) * 1.03
    krw_rub_rate = krw

    eur_rub_rate = eur

    rates_text = (
        f"EUR: <b>{eur:.2f} ₽</b>\n"
        f"USD: <b>{usd:.2f} ₽</b>\n"
        f"KRW: <b>{krw:.5f} ₽</b>\n"
    )

    return rates_text


# Обработчик команды /cbr
@bot.message_handler(commands=["cbr"])
def cbr_command(message):
    try:
        rates_text = get_currency_rates()

        # Создаем клавиатуру с кнопкой для расчета автомобиля
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("Главное меню", callback_data="main_menu")
        )

        # Отправляем сообщение с курсами и клавиатурой
        bot.send_message(
            message.chat.id, rates_text, reply_markup=keyboard, parse_mode="HTML"
        )
    except Exception as e:
        bot.send_message(
            message.chat.id, "Не удалось получить курсы валют. Попробуйте позже."
        )
        print(f"Ошибка при получении курсов валют: {e}")


# Обработчик команды /currencyrates
@bot.message_handler(commands=["currencyrates"])
def currencyrates_command(message):
    bot.send_message(message.chat.id, "Актуальные курсы валют: ...")


# Main menu creation function
def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(
        types.KeyboardButton(CALCULATE_CAR_TEXT),
        types.KeyboardButton(MANUAL_CAR_TEXT),
        types.KeyboardButton("Написать менеджеру"),
        types.KeyboardButton("Почему стоит выбрать нас?"),
        types.KeyboardButton("Мы в соц. сетях"),
        types.KeyboardButton("Написать в WhatsApp"),
    )
    return keyboard


# Start command handler
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user = message.from_user
    user_first_name = user.first_name

    welcome_message = (
        f"Здравствуйте, {user_first_name}!\n\n"
        "Я бот компании GetAuto. Я помогу вам расчитать стоимость понравившегося вам автомобиля из Южной Кореи до Владивостока\n\n"
        "Выберите действие из меню ниже"
    )
    bot.send_message(message.chat.id, welcome_message, reply_markup=main_menu())


# Error handling function
def send_error_message(message, error_text):
    global last_error_message_id

    # Remove previous error message if it exists
    if last_error_message_id.get(message.chat.id):
        try:
            bot.delete_message(message.chat.id, last_error_message_id[message.chat.id])
        except Exception as e:
            logging.error(f"Error deleting message: {e}")

    # Send new error message and store its ID
    error_message = bot.reply_to(message, error_text, reply_markup=main_menu())
    last_error_message_id[message.chat.id] = error_message.id
    logging.error(f"Error sent to user {message.chat.id}: {error_text}")


def get_car_info(url):
    global car_id_external, vehicle_no, vehicle_id, car_year, car_month

    # driver = create_driver()

    car_id_match = re.findall(r"\d+", url)
    car_id = car_id_match[0]
    car_id_external = car_id

    url = f"https://api.encar.com/v1/readside/vehicle/{car_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "http://www.encar.com/",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers).json()

    # Получаем все необходимые данные по автомобилю
    car_price = str(response["advertisement"]["price"])
    car_date = response["category"]["yearMonth"]

    year = car_date[2:4]
    month = car_date[4:]

    car_year = year
    car_month = month

    car_engine_displacement = str(response["spec"]["displacement"])
    car_type = response["spec"]["bodyName"]

    # Для получения данных по страховым выплатам
    vehicle_no = response["vehicleNo"]
    vehicle_id = response["vehicleId"]

    # Форматируем
    formatted_car_date = f"01{month}{year}"
    formatted_car_type = "crossover" if car_type == "SUV" else "sedan"

    print_message(
        f"ID: {car_id}\nType: {formatted_car_type}\nDate: {formatted_car_date}\nCar Engine Displacement: {car_engine_displacement}\nPrice: {car_price} KRW"
    )

    # Сохранение данных в базу
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO car_info (car_id, date, engine_volume, price, car_type)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (car_id) DO NOTHING
        """,
        (
            car_id,
            formatted_car_date,
            car_engine_displacement,
            car_price,
            formatted_car_type,
        ),
    )
    conn.commit()
    cursor.close()
    conn.close()
    print("Автомобиль был сохранён в базе данных")

    return [car_price, car_engine_displacement, formatted_car_date]


# Function to calculate the total cost
def calculate_cost(link, message):
    global car_data, car_id_external, car_month, car_year, krw_rub_rate, eur_rub_rate

    print_message("ЗАПРОС НА РАСЧЁТ АВТОМОБИЛЯ")

    # Отправляем сообщение и сохраняем его ID
    processing_message = bot.send_message(
        message.chat.id, "Обрабатываю данные. Пожалуйста подождите ⏳"
    )

    car_id = None

    # Проверка ссылки на мобильную версию
    if "fem.encar.com" in link:
        car_id_match = re.findall(r"\d+", link)
        if car_id_match:
            car_id = car_id_match[0]  # Use the first match of digits
            car_id_external = car_id
            link = f"https://fem.encar.com/cars/detail/{car_id}"
        else:
            send_error_message(message, "🚫 Не удалось извлечь carid из ссылки.")
            return
    else:
        # Извлекаем carid с URL encar
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        car_id = query_params.get("carid", [None])[0]

    result = get_car_info(link)
    car_price, car_engine_displacement, formatted_car_date = result

    if not car_price and car_engine_displacement and formatted_car_date:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                "Написать менеджеру", url="https://t.me/GetAuto_manager_bot"
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "Рассчитать стоимость другого автомобиля",
                callback_data="calculate_another",
            )
        )
        bot.send_message(
            message.chat.id, "Ошибка", parse_mode="Markdown", reply_markup=keyboard
        )
        bot.delete_message(message.chat.id, processing_message.message_id)
        return

    # Если есть новая ссылка
    if car_price and car_engine_displacement and formatted_car_date:
        car_engine_displacement = int(car_engine_displacement)

        # Форматирование данных
        formatted_car_year = f"20{car_year}"
        engine_volume_formatted = f"{format_number(car_engine_displacement)} cc"
        age = calculate_age(int(formatted_car_year), car_month)

        age_formatted = (
            "до 3 лет"
            if age == "0-3"
            else (
                "от 3 до 5 лет"
                if age == "3-5"
                else "от 5 до 7 лет" if age == "5-7" else "от 7 лет"
            )
        )

        # Конвертируем стоимость авто в рубли
        price_krw = int(car_price) * 10000
        car_price_rub = price_krw * krw_rub_rate

        response = get_customs_fees(
            car_engine_displacement,
            price_krw,
            int(f"20{car_year}"),
            car_month,
            engine_type=1,
        )

        # Таможенный сбор
        # customs_fee = calculate_customs_fee(car_price_rub)
        customs_fee = clean_number(response["sbor"])

        # Таможенная пошлина
        # car_price_eur = car_price_rub / eur_rub_rate
        # customs_duty = calculate_customs_duty(
        #     car_price_eur,
        #     int(round_engine_volume(car_engine_displacement)),
        #     eur_rub_rate,
        #     age_formatted.lower(),
        # )
        customs_duty = clean_number(response["tax"])

        # Рассчитываем утилизационный сбор
        # recycling_fee = calculate_recycling_fee(
        #     int(round_engine_volume(car_engine_displacement)), age_formatted.lower()
        # )
        recycling_fee = clean_number(response["util"])

        # Расчет итоговой стоимости автомобиля в рублях
        total_cost = (
            50000
            + (price_krw * krw_rub_rate)
            + (440000 * krw_rub_rate)
            + (100000 * krw_rub_rate)
            + (350000 * krw_rub_rate)
            + (600 * usd_rate)
            + customs_duty
            + customs_fee
            + recycling_fee
            + (346 * usd_rate)
            + 50000
            + 30000
            + 8000
        )

        total_cost_usd = total_cost / usd_rate
        total_cost_krw = total_cost / krw_rub_rate

        car_data["agent_korea_rub"] = 50000
        car_data["agent_korea_usd"] = 50000 / usd_rate
        car_data["agent_korea_krw"] = 50000 / krw_rub_rate

        car_data["advance_rub"] = 1000000 * krw_rub_rate
        car_data["advance_usd"] = (1000000 * krw_rub_rate) / usd_rate
        car_data["advance_krw"] = 1000000

        car_data["car_price_krw"] = price_krw - 1000000
        car_data["car_price_usd"] = (price_krw - 1000000) * krw_rub_rate / usd_rate
        car_data["car_price_rub"] = (price_krw - 1000000) * krw_rub_rate

        car_data["dealer_korea_usd"] = 440000 * krw_rub_rate / usd_rate
        car_data["dealer_korea_krw"] = 440000
        car_data["dealer_korea_rub"] = 440000 * krw_rub_rate

        car_data["delivery_korea_usd"] = 100000 * krw_rub_rate / usd_rate
        car_data["delivery_korea_krw"] = 100000
        car_data["delivery_korea_rub"] = 100000 * krw_rub_rate

        car_data["transfer_korea_usd"] = 350000 * krw_rub_rate / usd_rate
        car_data["transfer_korea_krw"] = 350000
        car_data["transfer_korea_rub"] = 350000 * krw_rub_rate

        car_data["freight_korea_usd"] = 600
        car_data["freight_korea_krw"] = 600 * usd_rate / krw_rub_rate
        car_data["freight_korea_rub"] = 600 * usd_rate

        car_data["korea_total_usd"] = (
            (50000 / usd_rate)
            + ((1000000 * krw_rub_rate) / usd_rate)
            + ((price_krw) * krw_rub_rate / usd_rate)
            + (440000 * krw_rub_rate / usd_rate)
            + (100000 * krw_rub_rate / usd_rate)
            + (350000 * krw_rub_rate / usd_rate)
            + (600)
        )

        car_data["korea_total_krw"] = (
            (50000 / krw_rub_rate)
            + (1000000)
            + (price_krw)
            + (440000)
            + (100000)
            + 350000
            + (600 * usd_rate / krw_rub_rate)
        )

        car_data["korea_total_rub"] = (
            (50000)
            + (1000000 * krw_rub_rate)
            + (price_krw * krw_rub_rate)
            + (440000 * krw_rub_rate)
            + (100000 * krw_rub_rate)
            + (350000 * krw_rub_rate)
            + (600 * usd_rate)
        )

        # Расходы Россия
        car_data["customs_duty_usd"] = customs_duty / usd_rate
        car_data["customs_duty_krw"] = customs_duty / krw_rub_rate
        car_data["customs_duty_rub"] = customs_duty

        car_data["customs_fee_usd"] = customs_fee / usd_rate
        car_data["customs_fee_krw"] = customs_fee / krw_rub_rate
        car_data["customs_fee_rub"] = customs_fee

        car_data["util_fee_usd"] = recycling_fee / usd_rate
        car_data["util_fee_krw"] = recycling_fee / krw_rub_rate
        car_data["util_fee_rub"] = recycling_fee

        car_data["broker_russia_usd"] = 346
        car_data["broker_russia_krw"] = 346 * usd_rate / krw_rub_rate
        car_data["broker_russia_rub"] = 346 * usd_rate

        car_data["svh_russia_usd"] = 50000 / usd_rate
        car_data["svh_russia_krw"] = 50000 / krw_rub_rate
        car_data["svh_russia_rub"] = 50000

        car_data["lab_russia_usd"] = 30000 / usd_rate
        car_data["lab_russia_krw"] = 30000 / krw_rub_rate
        car_data["lab_russia_rub"] = 30000

        car_data["perm_registration_russia_usd"] = 8000 / usd_rate
        car_data["perm_registration_russia_krw"] = 8000 / krw_rub_rate
        car_data["perm_registration_russia_rub"] = 8000

        preview_link = f"https://fem.encar.com/cars/detail/{car_id}"

        # Формирование сообщения результата
        result_message = (
            f"Возраст: {age_formatted}\n"
            f"Стоимость автомобиля в Корее: ₩{format_number(price_krw)}\n"
            f"Объём двигателя: {engine_volume_formatted}\n\n"
            f"Примерная стоимость автомобиля под ключ до Владивостока: \n<b>${format_number(total_cost_usd)} </b> | <b>₩{format_number(total_cost_krw)} </b> | <b>{format_number(total_cost)} ₽</b>\n\n"
            f"🔗 <a href='{preview_link}'>Ссылка на автомобиль</a>\n\n"
            "Если данное авто попадает под санкции, пожалуйста уточните возможность отправки в вашу страну у менеджера @GetAuto_manager_bot\n\n"
            "🔗 <a href='https://t.me/Getauto_kor'>Официальный телеграм канал</a>\n"
        )

        # Клавиатура с дальнейшими действиями
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("Детали расчёта", callback_data="detail")
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "Выплаты по ДТП",
                callback_data="technical_report",
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "Написать менеджеру", url="https://t.me/GetAuto_manager_bot"
            )
        )
        keyboard.add(
            types.InlineKeyboardButton(
                "Расчёт другого автомобиля",
                callback_data="calculate_another",
            )
        )

        bot.send_message(
            message.chat.id,
            result_message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        bot.delete_message(
            message.chat.id, processing_message.message_id
        )  # Удаляем сообщение о передаче данных в обработку

    else:
        send_error_message(
            message,
            "🚫 Произошла ошибка при получении данных. Проверьте ссылку и попробуйте снова.",
        )
        bot.delete_message(message.chat.id, processing_message.message_id)


# Function to get insurance total
def get_insurance_total():
    global car_id_external, vehicle_no, vehicle_id

    print_message("[ЗАПРОС] ТЕХНИЧЕСКИЙ ОТЧËТ ОБ АВТОМОБИЛЕ")

    formatted_vehicle_no = urllib.parse.quote(str(vehicle_no).strip())
    url = f"https://api.encar.com/v1/readside/record/vehicle/{str(vehicle_id)}/open?vehicleNo={formatted_vehicle_no}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": "http://www.encar.com/",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
        }

        response = requests.get(url, headers)
        json_response = response.json()

        # Форматируем данные
        damage_to_my_car = json_response["myAccidentCost"]
        damage_to_other_car = json_response["otherAccidentCost"]

        print(
            f"Выплаты по представленному автомобилю: {format_number(damage_to_my_car)}"
        )
        print(f"Выплаты другому автомобилю: {format_number(damage_to_other_car)}")

        return [format_number(damage_to_my_car), format_number(damage_to_other_car)]

    except Exception as e:
        print(f"Произошла ошибка при получении данных: {e}")
        return ["", ""]


# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    global car_data, car_id_external, usd_rate

    if call.data.startswith("detail") or call.data.startswith("detail_manual"):
        print_message("[ЗАПРОС] ДЕТАЛИЗАЦИЯ РАСЧËТА")

        detail_message = (
            f"<i>ПЕРВАЯ ЧАСТЬ ОПЛАТЫ</i>:\n\n"
            f"Агентские услуги по договору:\n<b>${format_number(car_data['agent_korea_usd'])}</b> | <b>₩{format_number(car_data['agent_korea_krw'])}</b> | <b>50000 ₽</b>\n\n"
            f"Задаток (бронь авто):\n<b>${format_number(car_data['advance_usd'])}</b> | <b>₩1,000,000</b> | <b>{format_number(car_data['advance_rub'])} ₽</b>\n\n\n"
            f"<i>ВТОРАЯ ЧАСТЬ ОПЛАТЫ</i>:\n\n"
            f"Стоимость автомобиля (за вычетом задатка):\n<b>${format_number(car_data['car_price_usd'])}</b> | <b>₩{format_number(car_data['car_price_krw'])}</b> | <b>{format_number(car_data['car_price_rub'])} ₽</b>\n\n"
            f"Диллерский сбор:\n<b>${format_number(car_data['dealer_korea_usd'])}</b> | <b>₩{format_number(car_data['dealer_korea_krw'])}</b> | <b>{format_number(car_data['dealer_korea_rub'])} ₽</b>\n\n"
            f"Доставка, снятие с учёта, оформление:\n<b>${format_number(car_data['delivery_korea_usd'])}</b> | <b>₩{format_number(car_data['delivery_korea_krw'])}</b> | <b>{format_number(car_data['delivery_korea_rub'])} ₽</b>\n\n"
            f"Транспортировка авто в порт:\n<b>${format_number(car_data['transfer_korea_usd'])}</b> | <b>₩{format_number(car_data['transfer_korea_krw'])}</b> | <b>{format_number(car_data['transfer_korea_rub'])} ₽</b>\n\n"
            f"Фрахт (Паром до Владивостока):\n<b>${format_number(car_data['freight_korea_usd'])}</b> | <b>₩{format_number(car_data['freight_korea_krw'])}</b> | <b>{format_number(car_data['freight_korea_rub'])} ₽</b>\n\n"
            f"<b>Итого расходов по Корее</b>:\n<b>${format_number(car_data['korea_total_usd'])}</b> | <b>₩{format_number(car_data['korea_total_krw'])}</b> | <b>{format_number(car_data['korea_total_rub'])} ₽</b>\n\n\n"
            f"<i>РАСХОДЫ РОССИЯ</i>:\n\n\n"
            f"Единая таможенная ставка:\n<b>${format_number(car_data['customs_duty_usd'])}</b> | <b>₩{format_number(car_data['customs_duty_krw'])}</b> | <b>{format_number(car_data['customs_duty_rub'])} ₽</b>\n\n"
            f"Таможенное оформление:\n<b>${format_number(car_data['customs_fee_usd'])}</b> | <b>₩{format_number(car_data['customs_fee_krw'])}</b> | <b>{format_number(car_data['customs_fee_rub'])} ₽</b>\n\n"
            f"Утилизационный сбор:\n<b>${format_number(car_data['util_fee_usd'])}</b> | <b>₩{format_number(car_data['util_fee_krw'])}</b> | <b>{format_number(car_data['util_fee_rub'])} ₽</b>\n\n\n"
            f"Брокер-Владивосток:\n<b>${format_number(car_data['broker_russia_usd'])}</b> | <b>₩{format_number(car_data['broker_russia_krw'])}</b> | <b>{format_number(car_data['broker_russia_rub'])} ₽</b>\n\n"
            f"СВХ-Владивосток:\n<b>${format_number(car_data['svh_russia_usd'])}</b> | <b>₩{format_number(car_data['svh_russia_krw'])}</b> | <b>{format_number(car_data['svh_russia_rub'])} ₽</b>\n\n"
            f"Лаборатория, СБКТС, ЭПТС:\n<b>${format_number(car_data['lab_russia_usd'])}</b> | <b>₩{format_number(car_data['lab_russia_krw'])}</b> | <b>{format_number(car_data['lab_russia_rub'])} ₽</b>\n\n"
            f"Временная регистрация-Владивосток:\n<b>${format_number(car_data['perm_registration_russia_usd'])}</b> | <b>₩{format_number(car_data['perm_registration_russia_krw'])}</b> | <b>{format_number(car_data['perm_registration_russia_rub'])} ₽</b>\n\n"
            f"<b>Доставку до вашего города уточняйте у менеджера @GetAuto_manager_bot</b>\n"
        )

        # Inline buttons for further actions
        keyboard = types.InlineKeyboardMarkup()

        if call.data.startswith("detail_manual"):
            keyboard.add(
                types.InlineKeyboardButton(
                    "Рассчитать стоимость другого автомобиля",
                    callback_data="calculate_another_manual",
                )
            )
        else:
            keyboard.add(
                types.InlineKeyboardButton(
                    "Рассчитать стоимость другого автомобиля",
                    callback_data="calculate_another",
                )
            )

        keyboard.add(
            types.InlineKeyboardButton(
                "Связаться с менеджером", url="https://t.me/GetAuto_manager_bot"
            )
        )

        bot.send_message(
            call.message.chat.id,
            detail_message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    elif call.data == "technical_report":
        bot.send_message(
            call.message.chat.id,
            "Запрашиваю отчёт по ДТП. Пожалуйста подождите ⏳",
        )

        # Retrieve insurance information
        insurance_info = get_insurance_total()

        # Проверка на наличие ошибки
        if (
            insurance_info is None
            or "Нет данных" in insurance_info[0]
            or "Нет данных" in insurance_info[1]
        ):
            error_message = (
                "Не удалось получить данные о страховых выплатах. \n\n"
                f'<a href="https://fem.encar.com/cars/report/accident/{car_id_external}">🔗 Посмотреть страховую историю вручную 🔗</a>\n\n\n'
                f"<b>Найдите две строки:</b>\n\n"
                f"보험사고 이력 (내차 피해) - Выплаты по представленному автомобилю\n"
                f"보험사고 이력 (타차 가해) - Выплаты другим участникам ДТП"
            )

            # Inline buttons for further actions
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    "Рассчитать стоимость другого автомобиля",
                    callback_data="calculate_another",
                )
            )
            keyboard.add(
                types.InlineKeyboardButton(
                    "Связаться с менеджером", url="https://t.me/GetAuto_manager_bot"
                )
            )

            # Отправка сообщения об ошибке
            bot.send_message(
                call.message.chat.id,
                error_message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        else:
            current_car_insurance_payments = (
                "0" if len(insurance_info[0]) == 0 else insurance_info[0]
            )
            other_car_insurance_payments = (
                "0" if len(insurance_info[1]) == 0 else insurance_info[1]
            )

            # Construct the message for the technical report
            tech_report_message = (
                f"Страховые выплаты по представленному автомобилю: \n<b>{current_car_insurance_payments} ₩</b>\n\n"
                f"Страховые выплаты другим участникам ДТП: \n<b>{other_car_insurance_payments} ₩</b>\n\n"
                f'<a href="https://fem.encar.com/cars/report/inspect/{car_id_external}">🔗 Ссылка на схему повреждений кузовных элементов 🔗</a>'
            )

            # Inline buttons for further actions
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    "Рассчитать стоимость другого автомобиля",
                    callback_data="calculate_another",
                )
            )
            keyboard.add(
                types.InlineKeyboardButton(
                    "Связаться с менеджером", url="https://t.me/GetAuto_manager_bot"
                )
            )

            bot.send_message(
                call.message.chat.id,
                tech_report_message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

    elif call.data == "calculate_another":
        bot.send_message(
            call.message.chat.id,
            "Пожалуйста, введите ссылку на автомобиль с сайта www.encar.com:",
        )

    elif call.data == "calculate_another_manual":
        user_id = call.message.chat.id
        user_manual_input[user_id] = {}  # Очищаем старые данные пользователя
        bot.send_message(user_id, "Введите месяц выпуска (например, 10 для октября):")
        bot.register_next_step_handler(call.message, process_manual_month)

    elif call.data == "main_menu":
        bot.send_message(
            call.message.chat.id, "📌 Главное меню", reply_markup=main_menu()
        )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global user_manual_input

    user_id = message.chat.id
    user_message = message.text.strip()

    # Проверяем нажатие кнопки "Рассчитать автомобиль"
    if user_message == CALCULATE_CAR_TEXT:
        bot.send_message(
            message.chat.id,
            "Пожалуйста, введите ссылку на автомобиль с сайта www.encar.com:",
        )

    elif user_message == MANUAL_CAR_TEXT:
        user_manual_input[user_id] = {}  # Создаём пустой словарь для пользователя
        bot.send_message(user_id, "Введите месяц выпуска (например, 10 для октября):")
        bot.register_next_step_handler(message, process_manual_month)

    # Проверка на корректность ссылки
    elif re.match(r"^https?://(www|fem)\.encar\.com/.*", user_message):
        calculate_cost(user_message, message)

    # Проверка на другие команды
    elif user_message == "Написать менеджеру":
        bot.send_message(
            message.chat.id,
            "Вы можете связаться с менеджером по ссылке: @GetAuto_manager_bot",
        )
    elif user_message == "Написать в WhatsApp":
        whatsapp_link = "https://wa.me/821030485191"  # Владимир Кан

        message_text = f"{whatsapp_link} - Владимир (Корея)"

        bot.send_message(
            message.chat.id,
            message_text,
        )
    elif user_message == "Почему стоит выбрать нас?":
        about_message = (
            "🔹 *Почему выбирают GetAuto?*\n\n"
            "🚗 *Экспертный опыт* — Мы знаем все нюансы подбора и доставки авто из Южной Кореи.\n\n"
            "🎯 *Индивидуальный подход* — Учитываем все пожелания клиентов, подбираем оптимальный вариант.\n\n"
            "🔧 *Комплексное обслуживание* — Полное сопровождение на всех этапах сделки.\n\n"
            "✅ *Гарантированное качество* — Проверенные авто, прозрачная история и состояние.\n\n"
            "💰 *Прозрачность ценообразования* — Честные цены, без скрытых платежей и комиссий.\n\n"
            "🚛 *Надежная логистика* — Организуем доставку авто в любую точку СНГ.\n\n"
            f"📲 Свяжитесь с нами и получите расчёт прямо сейчас! @GetAuto\\_manager\\_bot"
        )
        bot.send_message(message.chat.id, about_message, parse_mode="Markdown")

    elif user_message == "Мы в соц. сетях":
        channel_link = "https://t.me/Getauto_kor"
        instagram_link = "https://www.instagram.com/getauto_korea"
        youtube_link = "https://youtube.com/@getauto_korea"
        dzen_link = "https://dzen.ru/getauto_ru"
        vk_link = "https://vk.com/getauto_korea"

        message_text = f"Наш Телеграм Канал: \n{channel_link}\n\nНаш Инстаграм: \n{instagram_link}\n\nНаш YouTube Канал: \n{youtube_link}\n\nМы на Dzen: \n{dzen_link}\n\nМы в ВК: \n{vk_link}\n\n"

        bot.send_message(message.chat.id, message_text)

    else:
        bot.send_message(
            message.chat.id,
            "Пожалуйста, введите корректную ссылку на автомобиль с сайта www.encar.com или fem.encar.com.",
        )


#######################
# Для ручного расчёта #
#######################
# Обработчик ввода месяца
def process_manual_month(message):
    user_id = message.chat.id
    user_input = message.text.strip()

    # Проверяем, если пользователь нажал кнопку, а не ввёл число
    if user_input in [
        CALCULATE_CAR_TEXT,
        MANUAL_CAR_TEXT,
        "Написать менеджеру",
        "О нас",
        "Мы в соц. сетях",
        "Написать в WhatsApp",
    ]:
        handle_message(message)  # Передаём управление стандартному обработчику команд
        return  # Завершаем обработку ввода месяца

    # Проверяем корректность ввода месяца
    if not user_input.isdigit() or not (1 <= int(user_input) <= 12):
        bot.send_message(user_id, "❌ Некорректный месяц! Введите число от 1 до 12.")
        bot.register_next_step_handler(message, process_manual_month)
        return

    # Если всё ок, продолжаем ввод данных
    user_manual_input[user_id]["month"] = int(user_input)
    bot.send_message(
        user_id, "✅ Отлично! Теперь введите год выпуска (например, 2021):"
    )
    bot.register_next_step_handler(message, process_manual_year)


# Обработчик ввода года
def process_manual_year(message):
    user_id = message.chat.id
    user_input = message.text.strip()

    if not user_input.isdigit() or not (
        1980 <= int(user_input) <= datetime.datetime.now().year
    ):
        bot.send_message(
            user_id, "Некорректный год! Введите год от 1980 до текущего года:"
        )
        bot.register_next_step_handler(message, process_manual_year)
        return

    user_manual_input[user_id]["year"] = int(user_input)
    bot.send_message(user_id, "Введите объём двигателя в CC (например, 2000):")
    bot.register_next_step_handler(message, process_manual_engine)


# Обработчик ввода объёма двигателя
def process_manual_engine(message):
    user_id = message.chat.id
    user_input = message.text.strip()

    if not user_input.isdigit() or not (500 <= int(user_input) <= 10000):
        bot.send_message(
            user_id, "Некорректный объём! Введите число от 500 до 10000 CC:"
        )
        bot.register_next_step_handler(message, process_manual_engine)
        return

    user_manual_input[user_id]["engine_volume"] = int(user_input)
    bot.send_message(
        user_id, "Введите стоимость автомобиля в Корее (например, 30000000):"
    )
    bot.register_next_step_handler(message, process_manual_price)


# Обработчик ввода стоимости автомобиля
def process_manual_price(message):
    user_id = message.chat.id
    user_input = message.text.strip()

    if not user_input.isdigit() or not (1000000 <= int(user_input) <= 1000000000000):
        bot.send_message(
            user_id,
            "Некорректная стоимость! Введите сумму от 1 000 000 до 200 000 000 KRW:",
        )
        bot.register_next_step_handler(message, process_manual_price)
        return

    user_manual_input[user_id]["price_krw"] = int(user_input)

    # Запускаем расчёт автомобиля
    calculate_manual_cost(user_id)


# Функция расчёта стоимости авто
def calculate_manual_cost(user_id):
    data = user_manual_input[user_id]

    price_krw = data["price_krw"]
    engine_volume = data["engine_volume"]
    month = data["month"]
    year = data["year"]

    car_engine_displacement = int(engine_volume)

    # Форматирование данных
    engine_volume_formatted = f"{format_number(car_engine_displacement)} cc"
    age = calculate_age(year, month)
    age_formatted = (
        "до 3 лет"
        if age == "0-3"
        else (
            "от 3 до 5 лет"
            if age == "3-5"
            else "от 5 до 7 лет" if age == "5-7" else "от 7 лет"
        )
    )

    # Конвертируем стоимость авто в рубли
    price_krw = int(price_krw)

    response = get_customs_fees(
        car_engine_displacement,
        price_krw,
        year,
        month,
        engine_type=1,
    )

    customs_fee = clean_number(response["sbor"])
    customs_duty = clean_number(response["tax"])
    recycling_fee = clean_number(response["util"])

    # Расчет итоговой стоимости автомобиля в рублях
    total_cost = (
        50000
        + (price_krw * krw_rub_rate)
        + (440000 * krw_rub_rate)
        + (100000 * krw_rub_rate)
        + (350000 * krw_rub_rate)
        + (600 * usd_rate)
        + (customs_duty)
        + customs_fee
        + recycling_fee
        + (346 * usd_rate)
        + 50000
        + 30000
        + 8000
    )

    total_cost_usd = total_cost / usd_rate
    total_cost_krw = total_cost / krw_rub_rate

    car_data["agent_korea_rub"] = 50000
    car_data["agent_korea_usd"] = 50000 / usd_rate
    car_data["agent_korea_krw"] = 50000 / krw_rub_rate

    car_data["advance_rub"] = 1000000 * krw_rub_rate
    car_data["advance_usd"] = (1000000 * krw_rub_rate) / usd_rate
    car_data["advance_krw"] = 1000000

    car_data["car_price_krw"] = price_krw - 1000000
    car_data["car_price_usd"] = (price_krw - 1000000) * krw_rub_rate / usd_rate
    car_data["car_price_rub"] = (price_krw - 1000000) * krw_rub_rate

    car_data["dealer_korea_usd"] = 440000 * krw_rub_rate / usd_rate
    car_data["dealer_korea_krw"] = 440000
    car_data["dealer_korea_rub"] = 440000 * krw_rub_rate

    car_data["delivery_korea_usd"] = 100000 * krw_rub_rate / usd_rate
    car_data["delivery_korea_krw"] = 100000
    car_data["delivery_korea_rub"] = 100000 * krw_rub_rate

    car_data["transfer_korea_usd"] = 350000 * krw_rub_rate / usd_rate
    car_data["transfer_korea_krw"] = 350000
    car_data["transfer_korea_rub"] = 350000 * krw_rub_rate

    car_data["freight_korea_usd"] = 600
    car_data["freight_korea_krw"] = 600 * usd_rate / krw_rub_rate
    car_data["freight_korea_rub"] = 600 * usd_rate

    car_data["korea_total_usd"] = (
        (50000 / usd_rate)
        + ((1000000 * krw_rub_rate) / usd_rate)
        + ((price_krw) * krw_rub_rate / usd_rate)
        + (440000 * krw_rub_rate / usd_rate)
        + (100000 * krw_rub_rate / usd_rate)
        + (350000 * krw_rub_rate / usd_rate)
        + (600)
    )

    car_data["korea_total_krw"] = (
        (50000 / krw_rub_rate)
        + (1000000)
        + (price_krw)
        + (440000)
        + (100000)
        + 350000
        + (600 * usd_rate / krw_rub_rate)
    )

    car_data["korea_total_rub"] = (
        (50000)
        + (1000000 * krw_rub_rate)
        + (price_krw * krw_rub_rate)
        + (440000 * krw_rub_rate)
        + (100000 * krw_rub_rate)
        + (350000 * krw_rub_rate)
        + (600 * usd_rate)
    )

    # Расходы Россия
    car_data["customs_duty_usd"] = customs_duty / usd_rate
    car_data["customs_duty_krw"] = customs_duty * krw_rub_rate
    car_data["customs_duty_rub"] = customs_duty

    car_data["customs_fee_usd"] = customs_fee / usd_rate
    car_data["customs_fee_krw"] = customs_fee / krw_rub_rate
    car_data["customs_fee_rub"] = customs_fee

    car_data["util_fee_usd"] = recycling_fee / usd_rate
    car_data["util_fee_krw"] = recycling_fee / krw_rub_rate
    car_data["util_fee_rub"] = recycling_fee

    car_data["broker_russia_usd"] = 346
    car_data["broker_russia_krw"] = 346 * usd_rate / krw_rub_rate
    car_data["broker_russia_rub"] = 346 * usd_rate

    car_data["svh_russia_usd"] = 50000 / usd_rate
    car_data["svh_russia_krw"] = 50000 / krw_rub_rate
    car_data["svh_russia_rub"] = 50000

    car_data["lab_russia_usd"] = 30000 / usd_rate
    car_data["lab_russia_krw"] = 30000 / krw_rub_rate
    car_data["lab_russia_rub"] = 30000

    car_data["perm_registration_russia_usd"] = 8000 / usd_rate
    car_data["perm_registration_russia_krw"] = 8000 / krw_rub_rate
    car_data["perm_registration_russia_rub"] = 8000

    # Формирование сообщения
    result_message = (
        f"Возраст: {age_formatted}\n"
        f"Стоимость автомобиля в Корее: ₩{format_number(price_krw)}\n"
        f"Объём двигателя: {engine_volume_formatted}\n\n"
        f"Примерная стоимость автомобиля под ключ до Владивостока:\n"
        f"<b>${format_number(total_cost_usd)}</b> | "
        f"<b>₩{format_number(total_cost_krw)}</b> | "
        f"<b>{format_number(total_cost)} ₽</b>\n\n"
        "Если данное авто попадает под санкции, пожалуйста уточните возможность отправки в вашу страну у менеджера @GetAuto_manager_bot\n\n"
        "🔗 <a href='https://t.me/Getauto_kor'>Официальный телеграм канал</a>\n"
    )

    # Клавиатура с действиями
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Детали расчёта", callback_data="detail_manual")
    )
    keyboard.add(
        types.InlineKeyboardButton(
            "Рассчитать другой автомобиль", callback_data="calculate_another_manual"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            "Написать менеджеру", url="https://t.me/GetAuto_manager_bot"
        )
    )

    # Отправка сообщения пользователю
    bot.send_message(user_id, result_message, parse_mode="HTML", reply_markup=keyboard)


# Run the bot
if __name__ == "__main__":
    # initialize_db()
    get_currency_rates()
    set_bot_commands()
    bot.polling(non_stop=True)
