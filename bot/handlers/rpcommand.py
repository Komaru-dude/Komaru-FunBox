import json
import os
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db

rp_router = Router()

def rp_loader(file_path="rp_commands.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def rp_saver(commands, file_path="rp_commands.json"):
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(commands, file, ensure_ascii=False, indent=4)

@rp_router.message()
async def text(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Проверяем, если пользователь ещё не добавлен в базу данных, добавляем его
    if not db.user_exists(user_id):
        db.add_user(user_id)
    if not db.user_have_username(user_id):
        db.add_username(user_id, username=username.lstrip('@') if username else None)
    if not db.user_have_first_name(user_id):
        db.add_first_name(user_id, first_name)

