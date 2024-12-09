from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime, timedelta

time_router = Router()

# Команда для вычисления времени до Нового года 2025
@time_router.message(Command("new_year"))
async def time_to_new_year(message: Message):
    event_date = datetime(2025, 1, 1)
    now = datetime.now()
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

# Команда для вычисления времени до дня рождения кошек
@time_router.message(Command("birthdays"))
async def cats_birthdays(message: Message):
    cats = {
        "Комуги": datetime(2016, 3, 23),
        "Комару": datetime(2017, 5, 22),
        "Кокоа(воин кукурузных полей)": datetime(2019, 5, 12),
        "Панчан(ПАНТЯЯЯЯЯЯЯЯ)": datetime(2016, 12, 13),
        "Гома": datetime(2013, 10, 20),
        "Тобо-кун": datetime(2018, 4, 25),
        "Суу": datetime(2015, 2, 14),
        "Горомару": datetime(2015, 11, 10),
    }

    now = datetime.now()
    responses = []

    for name, birthday in cats.items():
        # Переносим день рождения в текущий или следующий год
        next_birthday = birthday.replace(year=now.year)
        if next_birthday < now:
            next_birthday = next_birthday.replace(year=now.year + 1)

        if next_birthday.date() == now.date():
            responses.append(f"🎉 Сегодня день рождения у {name}! Поздравьте кошку! 🎂")
        else:
            time_delta = next_birthday - now
            days = time_delta.days
            hours, remainder = divmod(time_delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            responses.append(
                f"{name}: через {days} дней, {hours} часов, {minutes} минут, {seconds} секунд (день рождения {next_birthday.date()})."
            )

    await message.reply("\n".join(responses))