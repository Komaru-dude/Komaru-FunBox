from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

strt_router = Router()

@strt_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет!\nЭтот бот на данный момент находится в разработке, данная команда будет сделана позже")
