import json, random, aiohttp
from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db
from bot.utils.aio_tools import make_post_request
from pathlib import Path

text_router = Router()
BASE_COMMANDS_PATH = Path("bot/basic_rp.json")
CUSTOM_DIR = Path("data/rp_commands")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "http://127.0.0.1:8001"

async def load_commands(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

async def get_chat_commands(chat_id: int):
    custom_path = CUSTOM_DIR / f"{chat_id}.json"
    if custom_path.exists():
        return {cmd["command"]: cmd for cmd in await load_commands(custom_path)}
    return {cmd["command"]: cmd for cmd in await load_commands(BASE_COMMANDS_PATH)}

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка API: статус {response.status}")
            return await response.json()

@text_router.message()
async def text(message: Message):
    user1 = message.from_user
    chat_id = message.chat.id
    text_msg = message.text

    if not db.user_exists(user1.id):
        db.add_user(user1.id)
    if not db.is_init(chat_id):
        db.init_chat_features(chat_id)
    if not text_msg:
        return

    if text_msg.lower() == "это что?" and message.reply_to_message and message.reply_to_message.text and db.is_feature_enabled(chat_id, "who"):
        request = message.reply_to_message.text
        payload = {
            "model": "gemini-2.0-flash",
            "request": {
                "messages": [{"role": "user", "content": request}]
            }
        }

        data, error = await make_post_request(payload)

        if error:
            await message.reply(error)
            return
        
        answer = data.get("answer", "⚠️ Ошибка: нет ответа от API")
        raw_answer = f"🧠 Ответ нейросети: {answer}"
        if len(raw_answer) > 4096:
            chunks = [raw_answer[i:i + 4096] for i in range(0, len(raw_answer), 4096)]
        else:
            chunks = [raw_answer]
        for chunk in chunks:
            await message.reply(chunk)
        return

    commands = await get_chat_commands(message.chat.id)

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
                    data = await fetch_json(f"{API_URL}/user/{username}")
                    if "user_id" in data:
                        user_id = data["user_id"]
                        name_data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{user_id}")
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
                    data = await fetch_json(f"{API_URL}/user/{username}")
                    if "user_id" in data:
                        user_id = data["user_id"]
                        name_data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{user_id}")
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