from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

pr_router = Router()

@pr_router.message(Command('privetbradok'))
async def cmd_privebradok(message: Message):
    await message.reply("Приве брадок!")