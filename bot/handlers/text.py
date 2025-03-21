import json, re
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db
from pathlib import Path

text_router = Router()
BASE_COMMANDS_PATH = Path("bot/basic_rp.json")
CUSTOM_DIR = Path("data/rp_commands")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

def load_commands(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
    
def get_chat_commands(chat_id: int):
    base_commands = load_commands(BASE_COMMANDS_PATH)
    custom_path = CUSTOM_DIR / f"{chat_id}.json"
    if custom_path.exists():
        custom_commands = load_commands(custom_path)
        return {**base_commands, **custom_commands}
    return base_commands

@text_router.message()
async def text(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    text_content = message.text

    # Проверка и регистрация пользователя
    if not db.user_exists(user_id):
        db.add_user(user_id)
    if not db.user_have_username(user_id):
        db.add_username(user_id, username=username.lstrip('@') if username else None)

    commands = get_chat_commands(message.chat.id)

    match = re.match(r'^/(\w+)', text_content)
    if not match:
        return

    command = match.group(1)
    if command not in commands:
        return

    response = commands[command]
    await message.answer(response, parse_mode=ParseMode.HTML)


    

