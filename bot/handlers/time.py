from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime
import pytz

time_router = Router()

# Определяем часовые пояса
moscow_tz = pytz.timezone('Europe/Moscow')
krsk_tz = pytz.timezone('Asia/Krasnoyarsk')

# Команда для вычисления времени до Нового года 2025
@time_router.message(Command("new_year"))
async def time_to_new_year(message: Message):
    command = message.text.strip().split()
    tz = moscow_tz  # По умолчанию Московское время
    if len(command) > 1 and command[1].lower() == "krsk":
        tz = krsk_tz  # Используем Красноярское время, если указано "krsk"

    event_date = datetime(2025, 1, 1, tzinfo=tz)
    now = datetime.now(tz)
    time_delta = event_date - now

    if time_delta.days <= 0 and time_delta.seconds <= 0:
        await message.reply("🎉 УРА! 2025 год уже наступил!")
        return

    days = time_delta.days
    hours, remainder = divmod(time_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    await message.reply(
        f"До 2025 года осталось: {days} дней, {hours} часов, {minutes} минут, {seconds} секунд!"
    )

@time_router.message(Command("birthdays"))
async def cats_birthdays(message: Message):
    command = message.text.strip().split()
    tz = moscow_tz
    if len(command) > 1 and command[1].lower() == "krsk":
        tz = krsk_tz

    cats = {
        "Комуги": tz.localize(datetime(2016, 3, 23)),
        "Комару": tz.localize(datetime(2017, 5, 22)),
        "Кокоа(кукурузный воин)": tz.localize(datetime(2019, 5, 12)),
        "Панчан(ПАНТЯЯЯЯЯЯЯЯ)": tz.localize(datetime(2016, 12, 13)),
        "Гома": tz.localize(datetime(2013, 10, 20)),
        "Тобо-кун": tz.localize(datetime(2018, 4, 25)),
        "Суу": tz.localize(datetime(2015, 2, 14)),
        "Горомару": tz.localize(datetime(2015, 11, 10)),
    }

    now = datetime.now(tz)
    responses = []

    for name, birthday in cats.items():
        # Переносим день рождения на текущий год
        next_birthday = birthday.replace(year=now.year)

        # Проверяем, совпадает ли текущая дата с днем рождения
        if next_birthday.date() == now.date():
            responses.append(f"🎉 Сегодня день рождения у {name}! Поздравьте кошку! 🎂")
            continue  # Пропускаем расчёт следующего дня рождения

        # Если день рождения уже прошёл, переносим его на следующий год
        if next_birthday < now:
            next_birthday = next_birthday.replace(year=now.year + 1)

        # Рассчитываем разницу во времени
        time_delta = next_birthday - now
        days, remainder = divmod(time_delta.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        responses.append(
            f"{name}: через {int(days)} дней, {int(hours)} часов, {int(minutes)} минут, {int(seconds)} секунд "
            f"(день рождения {next_birthday.date()})."
        )

    if responses:
        await message.reply("\n".join(responses))
    else:
        await message.reply("Непредвиденная ошибка во время выполнения команды.")