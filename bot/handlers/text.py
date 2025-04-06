import json
import random
import requests
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db
from pathlib import Path

text_router = Router()
BASE_COMMANDS_PATH = Path("bot/basic_rp.json")
CUSTOM_DIR = Path("data/rp_commands")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "http://127.0.0.1:8001"

def load_commands(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def get_chat_commands(chat_id: int):
    custom_path = CUSTOM_DIR / f"{chat_id}.json"
    if custom_path.exists():
        return {cmd["command"]: cmd for cmd in load_commands(custom_path)}
    return {cmd["command"]: cmd for cmd in load_commands(BASE_COMMANDS_PATH)}

@text_router.message()
async def text(message: Message):
    user1 = message.from_user
    text_msg = message.text

    if not db.user_exists(user1.id):
        db.add_user(user1.id)
    if not text_msg:
        return

    commands = get_chat_commands(message.chat.id)

    split_text = text_msg.split(maxsplit=1)
    command = split_text[0].lstrip('/')

    if command not in commands:
        return

    if not message.reply_to_message and len(split_text) < 2:
        await message.reply("Укажи пользователя после команды или ответь на его сообщение.")
        return

    target_user = None

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    else:
        entities = message.entities or []
        space_pos = text_msg.find(' ')
        args_start = space_pos + 1 if space_pos != -1 else len(text_msg)

        for entity in entities:
            if entity.offset < args_start:
                continue

            if entity.type == "text_mention":
                target_user = entity.user
                break
            elif entity.type == "mention":
                username = text_msg[entity.offset: entity.offset + entity.length].lstrip('@')
                try:
                    response = requests.get(f"{API_URL}/user/{username}")
                    data = response.json()
                    if "user_id" in data:
                        user_id = data["user_id"]
                        response_name = requests.get(f"{API_URL}/first_name/{message.chat.id}/{user_id}")
                        name_data = response_name.json()
                        target_user = type('User', (object,), {
                            "id": user_id,
                            "first_name": name_data.get("first_name", "Неизвестный")
                        })
                except Exception as e:
                    print(f"Ошибка при получении данных пользователя: {e}")
                break

        if not target_user and space_pos != -1:
            args = text_msg[space_pos+1:].split()
            if args:
                username = args[0].lstrip('@')
                try:
                    response = requests.get(f"{API_URL}/user/{username}")
                    data = response.json()
                    if "user_id" in data:
                        user_id = data["user_id"]
                        response_name = requests.get(f"{API_URL}/first_name/{message.chat.id}/{user_id}")
                        name_data = response_name.json()
                        target_user = type('User', (object,), {
                            "id": user_id,
                            "first_name": name_data.get("first_name", "Неизвестный")
                        })
                except Exception as e:
                    print(f"Ошибка при получении данных пользователя: {e}")

    if not target_user:
        await message.reply("Не удалось найти пользователя.")
        return

    # Форматируем пользователей
    user1_link = f'<a href="tg://user?id={user1.id}">{user1.first_name}</a>'
    user2_link = f'<a href="tg://user?id={target_user.id}">{target_user.first_name}</a>'

    # Получаем сообщение для команды
    cmd = commands[command]
    text_template = random.choice(cmd["messages"])
    result_text = text_template.format(user1=user1_link, user2=user2_link)

    if message.reply_to_message:
        await message.reply_to_message.reply(result_text, parse_mode=ParseMode.HTML)
    else:
        await message.answer(result_text, parse_mode=ParseMode.HTML)