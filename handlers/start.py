from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

strt_router = Router()

@strt_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет!\n"
                        "Это развлекательный бот созданный для кочон подвала.\n"
                        "Если хочешь узнать более подробную информацию о командах: /help")
