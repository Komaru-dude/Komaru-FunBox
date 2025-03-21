from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime
import pytz

time_router = Router()

# Определяем часовые пояса
moscow_tz = pytz.timezone('Europe/Moscow')

# Команда для вычисления времени до Нового года
@time_router.message(Command("new_year"))
async def time_to_new_year(message: Message):
    tz = moscow_tz  # По умолчанию Московское время

    # Задаём дату без часового пояса и локализуем её
    event_date = datetime(2026, 1, 1, 0, 0, 0)  # 1 января 2026 года, 00:00
    event_date = tz.localize(event_date)  # Локализуем дату в выбранной временной зоне
    
    now = datetime.now(tz)
    time_delta = event_date - now

    if time_delta.days < 0 or (time_delta.days == 0 and time_delta.seconds <= 0):
        await message.reply("🎉 УРА! 2026 год уже наступил!")
        return

    days = time_delta.days
    hours, remainder = divmod(time_delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    await message.reply(
        f"До 2026 года осталось: {days} дней, {hours} часов, {minutes} минут, {seconds} секунд!"
    )
