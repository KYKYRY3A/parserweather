from telegram import Update
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext
import requests
import logging
import sqlite3
from datetime import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ACCESS_KEY = "36ec1ad8-a27b-4713-ba85-99181e24c003"
ASK_CITY, CITY_STATE = range(2)
user_data = {}
notification_jobs = {}

def connect_db():
    return sqlite3.connect('data/cities.db')
def find_city(city_name):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT geo_lat, geo_lon FROM cities WHERE city = ?", (city_name,))
    result = cursor.fetchone()
    conn.close()
    return result

# /start
def start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    if user_id not in user_data or 'city' not in user_data[user_id]:
        update.message.reply_text("Привет! Пожалуйста, введите ваш город.")
        return ASK_CITY
    else:
        update.message.reply_text(
            "Привет! Я бот погоды. Выберите команду:\n"
            "/weather - узнать текущую погоду\n"
            "/forecast - получить прогноз на 10 дней\n"
            "/sub - подписаться на уведомления о погоде\n"
            "/selectcity - выбрать другой город"
        )
        return CITY_STATE

# обработка ввода города
def ask_city(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    city_name = update.message.text
    city_coords = find_city(city_name)
    if city_coords:
        user_data[user_id] = {'city': city_name, 'coords': city_coords}
        update.message.reply_text(
            "Город сохранен! Выберите команду:\n"
            "/weather - узнать текущую погоду\n"
            "/forecast - получить прогноз на 10 дней\n"
            "/sub - подписаться на уведомления о погоде\n"
            "/selectcity - выбрать другой город"
        )
        return CITY_STATE
    else:
        update.message.reply_text("Извините, я не знаю такого города. Пожалуйста, введите правильное название города.")
        return ASK_CITY

# /weather
def weather_command(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    if user_id in user_data and 'city' in user_data[user_id]:
        city_name = user_data[user_id]['city']
        city_coords = user_data[user_id]['coords']
        send_weather(update.message.chat_id, city_name, city_coords, context)
    else:
        update.message.reply_text("Пожалуйста, сначала введите ваш город.")
        return ASK_CITY

# погода
def send_weather(chat_id, city_name, city_coords, context):
    headers = {"X-Yandex-API-Key": ACCESS_KEY}
    try:
        response = requests.get(
            f'https://api.weather.yandex.ru/v2/forecast?lat={city_coords[0]}&lon={city_coords[1]}',
            headers=headers)
        if response.status_code == 200:
            data = response.json()
            weather_data = data['fact']
            condition = weather_data['condition']
            message = f"Текущая погода в {city_name}:\n"
            message += f"Температура: {weather_data['temp']}°C\n"
            message += f"Состояние: {translate_weather_condition(condition)}\n"
            message += f"Скорость ветра: {weather_data['wind_speed']} м/с\n"
            message += f"Влажность: {weather_data['humidity']}%\n"
            message += f"Давление: {weather_data['pressure_mm']} мм рт. ст."
            context.bot.send_message(chat_id, message)
        else:
            context.bot.send_message(chat_id, f"Ошибка при получении данных о погоде: {response.status_code}")
    except Exception as e:
        context.bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")

# перевод
def translate_weather_condition(condition):
    translations = {
        "clear": "ясно",
        "partly-cloudy": "переменная облачность",
        "cloudy": "облачно с прояснениями",
        "overcast": "пасмурно",
        "drizzle": "морось",
        "light-rain": "небольшой дождь",
        "rain": "дождь",
        "moderate-rain": "умеренно сильный дождь",
        "heavy-rain": "сильный дождь",
        "continuous-heavy-rain": "длительный сильный дождь",
        "showers": "ливень",
        "wet-snow": "дождь со снегом",
        "light-snow": "небольшой снег",
        "snow": "снег",
        "snow-showers": "снегопад",
        "hail": "град",
        "thunderstorm": "гроза",
        "thunderstorm-with-rain": "дождь с грозой",
        "thunderstorm-with-hail": "гроза с градом"
    }
    return translations.get(condition, condition)

# /forecast
def forecast_command(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    if user_id in user_data and 'city' in user_data[user_id]:
        city_name = user_data[user_id]['city']
        city_coords = user_data[user_id]['coords']
        send_forecast(update.message.chat_id, city_name, city_coords, context)
    else:
        update.message.reply_text("Пожалуйста, сначала введите ваш город.")
        return ASK_CITY

# погода на 10
def send_forecast(chat_id, city_name, city_coords, context):
    headers = {"X-Yandex-API-Key": ACCESS_KEY}
    try:
        response = requests.get(
            f'https://api.weather.yandex.ru/v2/forecast?lat={city_coords[0]}&lon={city_coords[1]}&limit=10',
            headers=headers)
        if response.status_code == 200:
            data = response.json()
            forecast_data = data['forecasts']
            message = f"Прогноз погоды в {city_name} на 10 дней:\n"
            for day in forecast_data:
                message += f"Дата: {day['date']}\n"
                message += f"Температура: {day['parts']['day']['temp_avg']}°C\n"
                message += f"Состояние: {translate_weather_condition(day['parts']['day']['condition'])}\n"
                message += f"Скорость ветра: {day['parts']['day']['wind_speed']} м/с\n"
                message += f"Влажность: {day['parts']['day']['humidity']}%\n"
                message += f"Давление: {day['parts']['day']['pressure_mm']} мм рт. ст.\n\n"
            context.bot.send_message(chat_id, message)
        else:
            context.bot.send_message(chat_id, f"Ошибка при получении прогноза погоды: {response.status_code}")
    except Exception as e:
        context.bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")

# рассылка
def send_daily_notification(context: CallbackContext) -> None:
    job = context.job
    chat_id = job.context
    user_id = chat_id

    if user_id in user_data and 'city' in user_data[user_id]:
        city_name = user_data[user_id]['city']
        city_coords = user_data[user_id]['coords']
        headers = {"X-Yandex-API-Key": ACCESS_KEY}
        try:
            response = requests.get(
                f'https://api.weather.yandex.ru/v2/forecast?lat={city_coords[0]}&lon={city_coords[1]}',
                headers=headers)
            if response.status_code == 200:
                data = response.json()
                weather_data = data['fact']
                condition = weather_data['condition']
                message = f"Доброе утро! Погода в {city_name} сегодня:\n"
                message += f"Температура: {weather_data['temp']}°C\n"
                message += f"Состояние: {translate_weather_condition(condition)}\n"
                message += f"Скорость ветра: {weather_data['wind_speed']} м/с\n"
                message += f"Влажность: {weather_data['humidity']}%\n"
                message += f"Давление: {weather_data['pressure_mm']} мм рт. ст."
                context.bot.send_message(chat_id, message)
            elif response.status_code == 403:
                context.bot.send_message(chat_id, f"Ошибка 403: доступ запрещен. Проверьте ваш API-ключ.")
                logger.error(f"Ошибка 403: доступ запрещен. Проверьте ваш API-ключ: {response.text}")
            else:
                context.bot.send_message(chat_id, f"Ошибка при получении данных о погоде: {response.status_code}")
        except Exception as e:
            context.bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")

# /sub
def sub_command(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    if user_id in user_data and 'city' in user_data[user_id]:
        chat_id = update.message.chat_id
        if chat_id in notification_jobs:
            update.message.reply_text("Вы уже подписаны на ежедневные уведомления о погоде.")
        else:
            job = context.job_queue.run_daily(send_daily_notification, time=time(hour=7, minute=0, second=0), context=chat_id)
            notification_jobs[chat_id] = job
            update.message.reply_text("Вы подписаны на ежедневные уведомления о погоде в 7:00.")
    else:
        update.message.reply_text("Пожалуйста, сначала введите ваш город.")
        return ASK_CITY

# /selectcity
def select_city_command(update: Update, context: CallbackContext) -> int:
    user_id = update.message.chat_id
    update.message.reply_text("Пожалуйста, введите новый город.")
    return ASK_CITY

# /unsub
def unsub_command(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    if chat_id in notification_jobs:
        job = notification_jobs[chat_id]
        job.schedule_removal()
        del notification_jobs[chat_id]
        update.message.reply_text("Вы отписаны от ежедневных уведомлений о погоде.")
    else:
        update.message.reply_text("Вы не подписаны на уведомления.")

# Для рассылки уведомлений
def send_hourly_notifications(context: CallbackContext) -> None:
    for chat_id in list(notification_jobs.keys()):
        try:
            user_id = chat_id
            if user_id in user_data and 'city' in user_data[user_id]:
                city_name = user_data[user_id]['city']
                city_coords = user_data[user_id]['coords']
                headers = {"X-Yandex-API-Key": ACCESS_KEY}
                response = requests.get(
                    f'https://api.weather.yandex.ru/v2/forecast?lat={city_coords[0]}&lon={city_coords[1]}',
                    headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    weather_data = data['fact']
                    condition = weather_data['condition']
                    message = f"Текущая погода в {city_name}:\n"
                    message += f"Температура: {weather_data['temp']}°C\n"
                    message += f"Состояние: {translate_weather_condition(condition)}\n"
                    message += f"Скорость ветра: {weather_data['wind_speed']} м/с\n"
                    message += f"Влажность: {weather_data['humidity']}%\n"
                    message += f"Давление: {weather_data['pressure_mm']} мм рт. ст."
                    context.bot.send_message(chat_id, message)
                elif response.status_code == 403:
                    context.bot.send_message(chat_id, f"Ошибка 403: доступ запрещен. Проверьте ваш API-ключ.")
                    logger.error(f"Ошибка 403: доступ запрещен. Проверьте ваш API-ключ: {response.text}")
                else:
                    context.bot.send_message(chat_id, f"Ошибка при получении данных о погоде: {response.status_code}")
            else:
                context.bot.send_message(chat_id, "Пожалуйста, укажите ваш город с помощью команды /start.")
        except Exception as e:
            logger.error(f"Произошла ошибка при отправке уведомления: {str(e)}")

def main():
    updater = Updater("7094495591:AAGiVUI76em8hf67dLh6Fq-0S4xgeeoVe6k", use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_CITY: [MessageHandler(Filters.text & ~Filters.command, ask_city)],
            CITY_STATE: [
                CommandHandler('weather', weather_command),
                CommandHandler('forecast', forecast_command),
                CommandHandler('sub', sub_command),
                CommandHandler('unsub', unsub_command),
                CommandHandler('selectcity', select_city_command)
            ],
        },
        fallbacks=[]
    )

    dp.add_handler(conv_handler)

    job_minute = updater.job_queue.run_repeating(send_hourly_notifications, interval=60, first=0)

    updater.start_polling()
    updater.idle()
if __name__ == '__main__':
    main()
