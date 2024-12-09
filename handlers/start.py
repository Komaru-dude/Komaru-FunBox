from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

strt_router = Router()

@strt_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет!\n"
                        "На данный момент доступны эти команды:\n\n"
                        "/start - Ты ввёл её совсем недавно\n"
                        "/new_year - Отсчёт до нового года\n"
                        "/birthdays - Отсчёты до дней рождения кошек\n")
