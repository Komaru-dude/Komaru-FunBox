import json
import os
import random
import re
import traceback
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import openai
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database.database import Database
from bot.handlers.ai.text_ai import (
    process_active_chat,
    process_explain_reply,
    process_user_prompt_trigger,
)
from bot.handlers.video import cmd_video
from bot.utils.aio_tools import error_report, fetch_user_data, get_user_id

text_router = Router()
BASE_COMMANDS_PATH = Path("bot/config/basic_rp.json")
CUSTOM_DIR = Path("data/rp_commands")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
SUPPORTED_DOMAINS = [
    "youtube.com",
    "youtu.be",
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


@text_router.message(F.text)
async def text(message: Message, bot: Bot, state: FSMContext, db: Database):
    try:
        assert message.from_user is not None
        assert message.text is not None
        user1 = message.from_user
        chat_id = message.chat.id
        text_msg = message.text

        handled = await process_active_chat(message, state, db, text_msg)
        if handled:
            return

        handled = await process_user_prompt_trigger(message, db, text_msg)
        if handled:
            return

        handled = await process_explain_reply(message, db)
        if handled:
            return

        if message.chat.type in ["channel", "private"]:
            return
        await db.update_message_count(user1.id, chat_id)
        if not text_msg:
            return
        commands = await get_chat_commands(chat_id)
        clean_text = text_msg.lstrip("/").strip().lower()

        sorted_commands = sorted(commands.keys(), key=len, reverse=True)
        matched_command = None

        for cmd in sorted_commands:
            if clean_text.startswith(cmd):
                end_pos = len(cmd)
                if len(clean_text) > end_pos and not clean_text[end_pos].isspace():
                    continue
                matched_command = cmd
                break

        if text_msg.startswith(("http://", "https://")) and await db.is_setting_enabled(
            chat_id, "autovideo"
        ):
            parsed_url = urlparse(message.text)
            domain = parsed_url.netloc.lower().replace("www.", "")
            if any(
                domain.endswith(supported) for supported in SUPPORTED_DOMAINS
            ) and await db.is_command_available(user1.id, "video", 300):
                await cmd_video(message, bot, db, url=message.text)
                return
        elif matched_command:
            remaining_text = clean_text[len(matched_command) :].strip()

            if not message.reply_to_message and not remaining_text:
                await message.reply(
                    "Укажи пользователя после команды или ответь на его сообщение."
                )
                return

            target_user_id, error_msg = await get_user_id(message)
            if not target_user_id:
                await message.reply(error_msg or "Не удалось найти пользователя.")
                return

            user_data = await fetch_user_data(user_id=target_user_id, chat_id=chat_id)
            if not user_data or "error" in user_data:
                await message.reply(user_data.get("error", "Ошибка получения данных"))
                return

            user1_link = f'<a href="tg://user?id={user1.id}">{user1.first_name}</a>'
            user2_link = f'<a href="tg://user?id={target_user_id}">{user_data.get("first_name", "Пользователь")}</a>'

            cmd = commands[matched_command]
            text_template = random.choice(cmd["messages"])
            result_text = text_template.format(user1=user1_link, user2=user2_link)

            if message.reply_to_message:
                await message.reply_to_message.reply(
                    result_text, parse_mode=ParseMode.HTML
                )
            else:
                await message.answer(result_text, parse_mode=ParseMode.HTML)
            return

        clean_text = re.sub(r"[^\w\s]", "", text_msg.lower())

        words = clean_text.split()

        if any(
            word in words for word in ("alo", "ало", "алё", "ale")
        ) and await db.is_setting_enabled(chat_id, "alo"):
            await message.reply("📞 В очко себе поалёкай")
            return

        if any(
            word in words for word in ("ау", "ay", "au")
        ) and await db.is_setting_enabled(chat_id, "alo"):
            await message.reply("🪵 В лесу аукай, себе в сраку себе")
            return

        if text_msg.lower() == "/бонум" and await db.is_command_available(
            user1.id, "bonum_ru", 5
        ):
            await bot.send_sticker(
                message.chat.id,
                "CAACAgIAAyEFAASbCRfOAAJW2mjT7S6mjNl2eq1K3OsShmsV2K8AAzotAAIEtJhLnn7lET7JhBM2BA",
                reply_to_message_id=message.message_id,
            )

    except openai.InternalServerError:
        await message.reply("⚠️ Внутренняя ошибка API")
    except openai.RateLimitError:
        models_list = os.getenv("ONLYSQ_ALLOWED_FREE_MODELS", "").split(",")
        free_models = [m.strip() for m in models_list if m.strip()]
        models_text = ", ".join(f"<code>{m}</code>" for m in free_models[:5])
        await message.reply(
            f"❌ Превышен лимит RPM для данной модели.\n\n"
            f"🔄 Попробуйте:\n"
            f"- Подождать несколько минут\n"
            f"- Выбрать другую модель (например: {models_text})\n\n"
            f"<i>Используйте /available_models для просмотра доступных моделей</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "text", traceback.format_exc())
