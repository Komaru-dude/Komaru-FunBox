from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import random

random_router = Router()

@random_router.message(Command("random"))
async def cmd_random(message: Message):

    responses = [
        "Да, без сомнений!",
        "Нет, это не сбудется.",
        "Возможно, ты прав.",
        "Скорее всего, да.",
        "Попробуй снова позже.",
        "Определенно нет.",
        "Я бы сказал да.",
    ]
    response = random.choice(responses)
    
    await message.answer(response)