import json
import random
import traceback
from pathlib import Path
from urllib.parse import urlparse
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db
from bot.handlers.ai import cmd_gemini
from bot.handlers.video import cmd_video
from bot.utils.aio_tools import get_user_id, fetch_user_data, error_report

text_router = Router()
BASE_COMMANDS_PATH = Path("bot/basic_rp.json")
CUSTOM_DIR = Path("data/rp_commands")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
SUPPORTED_DOMAINS = [
    "tiktok.com", "soundcloud.com", "vimeo.com",
    "twitch.tv", "bilibili.com", "facebook.com",
    "rumble.com", "odysee.com", "dailymotion.com", "vk.com"
    # добавить позже ещё
]

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

@text_router.message()
async def text(message: Message, bot: Bot):
    try:
        user1 = message.from_user
        chat_id = message.chat.id
        text_msg = message.text

        if message.chat.type == "channel":
            return
        if not db.user_exists(user1.id, chat_id):
            db.add_user(user1.id, chat_id)
        if not db.is_init(chat_id):
            db.init_chat_features(chat_id)
        if not text_msg:
            return

        if (
            text_msg.lower() == "это что?"
            and message.reply_to_message
            and message.reply_to_message.text
            and db.is_feature_enabled(chat_id, "who")
        ):
            request = f"Твоя задача кратко объяснить что такое, вот запрос пользователя: {message.reply_to_message.text}"
            custom_payload = {
                "model": "gemini-2.0-flash",
                "request": {
                    "messages": [{"role": "user", "content": request}]
                }
            }
            await cmd_gemini(message, bot, custom_payload=custom_payload)
            return
        elif message.text.startswith(("http://", "https://")) and db.is_feature_enabled(chat_id, "autovideo"):
            parsed_url = urlparse(message.text)
            domain = parsed_url.netloc.lower().replace("www.", "")
            if any(domain.endswith(supported) for supported in SUPPORTED_DOMAINS):
                await cmd_video(message, bot, url=message.text)
                return

        commands = await get_chat_commands(chat_id)
        split_text = text_msg.split(maxsplit=1)
        command = split_text[0].lstrip('/').lower()

        if command not in commands:
            return

        if not message.reply_to_message and len(split_text) < 2:
            await message.reply("Укажи пользователя после команды или ответь на его сообщение.")
            return

        target_user_id, error_msg = await get_user_id(message)
        if not target_user_id:
            await message.reply(error_msg or "Не удалось найти пользователя.")
            return

        user_data = await fetch_user_data(user_id=target_user_id, chat_id=chat_id)
        if not user_data or 'error' in user_data:
            await message.reply(user_data.get('error', 'Ошибка получения данных'))
            return

        user1_link = f'<a href="tg://user?id={user1.id}">{user1.first_name}</a>'
        user2_link = f'<a href="tg://user?id={target_user_id}">{user_data.get("first_name", "Пользователь")}</a>'

        cmd = commands[command]
        text_template = random.choice(cmd["messages"])
        result_text = text_template.format(user1=user1_link, user2=user2_link)

        if message.reply_to_message:
            await message.reply_to_message.reply(result_text, parse_mode=ParseMode.HTML)
        else:
            await message.answer(result_text, parse_mode=ParseMode.HTML)
    except Exception:
        await error_report(message, bot, "text", traceback.format_exc())