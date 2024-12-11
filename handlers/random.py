from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import random

random_router = Router()

@random_router.message(Command("random"))
async def cmd_random(message: Message):
    parts = message.text.split()
    
    # Если после команды нет дополнительных аргументов, просто выводим случайный ответ
    if len(parts) == 1:
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
    else:
        # В случае, если после команды есть аргументы
        response = " ".join(parts[1:])
    
    await message.answer(response)