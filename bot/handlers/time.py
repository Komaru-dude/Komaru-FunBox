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

    # Задаём дату без часового пояса и локализуем её
    event_date = datetime(2025, 1, 1, 0, 0, 0)  # 1 января 2025 года, 00:00
    event_date = tz.localize(event_date)  # Локализуем дату в выбранной временной зоне
    
    now = datetime.now(tz)
    time_delta = event_date - now

    if time_delta.days < 0 or (time_delta.days == 0 and time_delta.seconds <= 0):
        await message.reply("🎉 УРА! 2025 год уже наступил!")
        return

    days = time_delta.days
    hours, remainder = divmod(time_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    await message.reply(
        f"До 2025 года осталось: {days} дней, {hours} часов, {minutes} минут, {seconds} секунд!"
    )
