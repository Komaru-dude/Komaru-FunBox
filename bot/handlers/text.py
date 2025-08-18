import asyncio
import json
import os
import random
import re
import time
import traceback
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import openai
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot import logger
from bot.database import Database
from bot.handlers.ai import ChatState, cmd_ai
from bot.handlers.video import cmd_video
from bot.utils.aio_tools import error_report, fetch_user_data, get_user_id
from bot.utils.global_storage import active_chats, onlysq_models

text_router = Router()
BASE_COMMANDS_PATH = Path("bot/config/basic_rp.json")
PROMPT_TRIGGER_PREFIX = "!"
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
        user1 = message.from_user
        chat_id = message.chat.id
        text_msg = message.text

        current_state = await state.get_state()
        if current_state == ChatState.active.state:
            if message.chat.id not in active_chats:
                await state.clear()
                return
            base_msg = await message.reply("🔄 Обработка...")
            user_data = await state.get_data()
            messages = user_data.get("messages", [])
            model = user_data.get("model", "gemini-2.0-flash")
            user_message = text_msg.strip()

            messages.append({"role": "user", "content": user_message})

            client = openai.AsyncOpenAI(
                api_key=os.getenv("ONLYSQ_API_KEY"),
                base_url=os.getenv("OPENAI_SDK_API_URL"),
            )

            can_stream = onlysq_models["models"].get(model, {}).get("can-stream", False)
            model_info = onlysq_models["models"].get(model, {})
            model_display_name = model_info.get("name", model)

            if can_stream:
                final_text = ""
                buffer = ""
                edited_once = False
                last_edit_time = time.monotonic()

                async for chunk in await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                ):
                    delta = chunk.choices[0].delta.content
                    if delta:
                        final_text += delta
                        buffer += delta

                        now = time.monotonic()
                        if (
                            len(buffer) > 30
                            or delta.endswith((".", "!", "?", "\n"))
                            or now - last_edit_time > 3.0
                        ):
                            try:
                                await base_msg.edit_text(
                                    f"💭 Запрос: {user_message}\n"
                                    f"🧠 Модель: {model_display_name}\n\n"
                                    f"📝 Ответ: {final_text}"
                                )
                                buffer = ""
                                edited_once = True
                                last_edit_time = now
                            except TelegramRetryAfter as e:
                                await asyncio.sleep(e.retry_after)
                            except Exception:
                                pass
                        elif not edited_once:
                            try:
                                await base_msg.edit_text(
                                    f"💭 Запрос: {user_message}\n"
                                    f"🧠 Модель: {model_display_name}\n\n"
                                    f"📝 Ответ: {final_text}"
                                )
                            except Exception:
                                pass

                messages.append({"role": "assistant", "content": final_text})
                if len(messages) > 8:
                    messages = [messages[0]] + messages[-7:]
                await state.update_data(messages=messages)
            else:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                )
                choices = response.choices
                if not choices:
                    raise ValueError("Нет ответа от API")

                answer_content = choices[0].message.content
                if model == "deepseek-r1":
                    answer = re.sub(
                        r"<think>.*?</think>", "", answer_content, flags=re.DOTALL
                    ).strip()
                elif model == "gemini-2.5-flash":
                    answer = re.sub(
                        r"<thought>.*?</thought>", "", answer_content, flags=re.DOTALL
                    ).strip()
                else:
                    answer = answer_content
                raw_answer = (
                    f"💭 Запрос: {user_message}\n"
                    f"🧠 Модель: {model_display_name}\n\n"
                    f"📝 Ответ: {answer}"
                )

                chunks = [
                    raw_answer[i : i + 4096] for i in range(0, len(raw_answer), 4096)
                ]

                for idx, chunk in enumerate(chunks):
                    if idx == 0:
                        await base_msg.edit_text(chunk)
                    else:
                        await message.reply(chunk)

                ai_response = response.choices[0].message.content
                ai_response = re.sub(r"[*_`#]", "", ai_response).strip()

                messages.append({"role": "assistant", "content": ai_response})
                if len(messages) > 8:
                    messages = [messages[0]] + messages[-7:]

                await state.update_data(messages=messages)

                chunks = [
                    ai_response[i : i + 4096] for i in range(0, len(ai_response), 4096)
                ]
                for idx, chunk in enumerate(chunks):
                    if idx == 0:
                        await base_msg.edit_text(chunk)
                    else:
                        await message.answer(chunk)
            return

        if message.chat.type == "channel":
            return
        await db.update_message_count(user1.id, chat_id)
        if not text_msg:
            return
        if await db.is_setting_enabled(chat_id, "give_random_rep"):
            chance = await db.get_setting(chat_id, "random_rep")
            roll = random.random()
            logger.debug(f"🎲 Проверка шанса: выпало {roll}, шанс {chance}")
            if roll < chance:
                await db.update_reputation(user1.id, chat_id, "auto_add")
                logger.debug(f"✅ Пользователю выдана репутация: {user1.id}")

        commands = await get_chat_commands(chat_id)
        clean_text = text_msg.lstrip('/').strip().lower()
        
        sorted_commands = sorted(commands.keys(), key=len, reverse=True)
        matched_command = None
        
        for cmd in sorted_commands:
            if clean_text.startswith(cmd):
                end_pos = len(cmd)
                if len(clean_text) > end_pos and not clean_text[end_pos].isspace():
                    continue
                matched_command = cmd
                break

        if (
            text_msg.lower() == "это что?"
            and message.reply_to_message
            and message.reply_to_message.text
            and await db.is_setting_enabled(chat_id, "who")
        ):
            messages = [
                {
                    "role": "system",
                    "content": "Твоя задача кратко объяснить то что спрашивает пользователь. Если ответ содержит материалы для взрослых (18+), представь информацию корректно и деликатно, смягчив формулировки. Не используй markdown/html/latex форматирование.",
                },
                {"role": "user", "content": message.reply_to_message.text},
            ]
            answer = await cmd_ai(messages=messages, cli_mode=True)
            await message.reply(f"📝 Ответ: {answer}")
            return
        elif text_msg.startswith(PROMPT_TRIGGER_PREFIX) and await db.is_setting_enabled(
            chat_id, "user_prompts"
        ):
            match = re.match(
                rf"^{re.escape(PROMPT_TRIGGER_PREFIX)}(\S+)\s*(.*)", text_msg
            )
            if match:
                prompt_name = match.group(1)
                user_query = match.group(2)

                prompt = await db.get_prompt_by_title(prompt_name, user1.id)
                if not prompt:
                    await message.reply(
                        f"❌ Промпт <b>{escape(prompt_name)}</b> не найден.",
                        parse_mode=ParseMode.HTML,
                    )
                    return

                prompt_content = prompt["content"]
                messages_for_ai = [
                    {"role": "system", "content": prompt_content},
                    {"role": "user", "content": user_query},
                ]
                await cmd_ai(
                    message=message,
                    bot=bot,
                    messages=messages_for_ai,
                    db=db,
                )
                return
        elif text_msg.startswith(
            ("http://", "https://")
        ) and await db.is_setting_enabled(chat_id, "autovideo"):
            parsed_url = urlparse(message.text)
            domain = parsed_url.netloc.lower().replace("www.", "")
            if any(domain.endswith(supported) for supported in SUPPORTED_DOMAINS):
                await cmd_video(message, bot, url=message.text)
                return
        elif matched_command:
            remaining_text = clean_text[len(matched_command):].strip()
            
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

    except openai.InternalServerError:
        await message.reply("⚠️ Внутренняя ошибка API")
    except openai.RateLimitError:
        await message.reply("❌ Превышен лимит запросов к API. Попробуйте позже")
    except Exception:
        await error_report(message, bot, "text", traceback.format_exc())
