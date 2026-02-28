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
from bot.database.database import Database
from bot.handlers.ai import (
    DEFAULT_MODEL,
    TOOLS_SCHEMA,
    ChatState,
    handle_tool_call,
)
from bot.handlers.video import cmd_video
from bot.utils.ai_api import simple_text_api, stream_text_api
from bot.utils.aio_tools import error_report, fetch_user_data, get_user_id
from bot.utils.global_storage import active_chats, onlysq_models
from bot.utils.premium_logic import is_model_available_for_user

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

        current_state = await state.get_state()
        if current_state == ChatState.active.state:
            if message.chat.id not in active_chats:
                await state.clear()
                return

            base_msg = await message.reply("🔄 Обработка...")
            user_data = await state.get_data()
            messages = user_data.get("messages", [])
            model = user_data.get("model", DEFAULT_MODEL)
            user_message = text_msg.strip()

            user_tier = await db.get_user_tier(user1.id)
            if not is_model_available_for_user(model, user_tier):
                await state.clear()
                tier_name = "премиумные" if user_tier > 0 else "свободные"
                await base_msg.edit_text(
                    f"❌ Модель <code>{model}</code> недоступна в вашем тарифе.\n\n"
                    f"🔄 Сброс на стандартную модель: <code>{DEFAULT_MODEL}</code>\n\n"
                    f"🔧 Используйте <code>/set_def_model имя_модели</code> для установки модели по умолчанию\n"
                    f"📋 Используйте <code>/available_models</code> для просмотра {tier_name} моделей",
                    parse_mode=ParseMode.HTML,
                )
                return

            messages.append({"role": "user", "content": user_message})

            client = openai.AsyncOpenAI(
                api_key=os.getenv("ONLYSQ_API_KEY"),
                base_url=os.getenv("OPENAI_SDK_API_URL"),
            )

            model_info = onlysq_models["models"].get(model, {})
            model_display_name = model_info.get("name", model)

            is_gemini_tool_model = model.startswith("gemini")

            if is_gemini_tool_model:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto",
                )

                response_message = response.choices[0].message
                final_text = ""

                if response_message.tool_calls:

                    temp_messages = []

                    for tool_call in response_message.tool_calls:
                        tool_output = await handle_tool_call(tool_call, message, state)
                        temp_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_output["output"],
                            }
                        )

                    messages.append(response_message)
                    messages.extend(temp_messages)

                    final_text = await simple_text_api(
                        model=model,
                        messages=messages,
                    )
                else:
                    final_text = response_message.content

                answer = re.sub(
                    r"<thought>.*?</thought>", "", final_text, flags=re.DOTALL
                ).strip()

                current_state = await state.get_state()
                if current_state == ChatState.active.state:
                    messages.append({"role": "assistant", "content": answer})
                    if len(messages) > 8:
                        messages = [messages[0]] + messages[-7:]
                    await state.update_data(messages=messages)

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
                        await message.answer(chunk)

            else:

                can_stream = model_info.get("can-stream", False)

                if can_stream:
                    final_text = ""
                    buffer = ""
                    edited_once = False
                    last_edit_time = time.monotonic()

                    async for chunk in stream_text_api(
                        model=model,
                        messages=messages,
                    ):
                        if chunk:
                            final_text += chunk
                            buffer += chunk

                            now = time.monotonic()
                            if (
                                len(buffer) > 35
                                or chunk.endswith((".", "!", "?", "\n"))
                                or now - last_edit_time > 10.0
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
                    response = await simple_text_api(
                        model=model,
                        messages=messages,
                    )
                    if not response:
                        raise ValueError("Нет ответа от API")

                    answer_content = response
                    if model == "deepseek-r1":
                        answer = re.sub(
                            r"<think>.*?</think>", "", answer_content, flags=re.DOTALL
                        ).strip()
                    elif model == "gemini-2.5-flash":
                        answer = re.sub(
                            r"", "", answer_content, flags=re.DOTALL
                        ).strip()
                    else:
                        answer = answer_content
                    raw_answer = (
                        f"💭 Запрос: {user_message}\n"
                        f"🧠 Модель: {model_display_name}\n\n"
                        f"📝 Ответ: {answer}"
                    )

                    chunks = [
                        raw_answer[i : i + 4096]
                        for i in range(0, len(raw_answer), 4096)
                    ]

                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            await base_msg.edit_text(chunk)
                        else:
                            await message.answer(chunk)

                    ai_response = response
                    ai_response = re.sub(r"[*_`#]", "", ai_response).strip()

                    messages.append({"role": "assistant", "content": ai_response})
                    if len(messages) > 8:
                        messages = [messages[0]] + messages[-7:]

                    await state.update_data(messages=messages)

            return

        user_prompt_trigger = await db.get_user_setting(
            user1.id, "custom_prompts_trigger"
        )

        if text_msg.startswith(user_prompt_trigger) and await db.is_setting_enabled(
            chat_id, "user_prompts"
        ):
            match = re.match(
                rf"^{re.escape(user_prompt_trigger)}(\S+)\s*(.*)", text_msg
            )
            if match:
                prompt_name = match.group(1)
                user_query = match.group(2)
                reply_query = ""

                # Парсим reply
                if message.reply_to_message:
                    if message.reply_to_message.text:
                        reply_query = message.reply_to_message.text
                    elif message.reply_to_message.caption:
                        reply_query = message.reply_to_message.caption
                    user_query = reply_query + (" " if user_query else "") + user_query

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

                # Получаем пользовательскую модель
                user_data = await db.get_user_data(user1.id, chat_id)
                user_default_model = user_data.get("default_model", DEFAULT_MODEL)
                model = user_default_model
                model_match = re.search(r"-m\s+(\S+)", user_query)
                if model_match:
                    model_candidate = model_match.group(1)
                    if model_candidate in onlysq_models["models"]:
                        model = model_candidate
                        user_query = re.sub(r"-m\s+\S+", "", user_query).strip()
                        messages_for_ai[1]["content"] = user_query

                user_tier = await db.get_user_tier(user1.id)
                if not is_model_available_for_user(model, user_tier):
                    tier_name = "премиумные" if user_tier > 0 else "свободные"
                    await message.reply(
                        f"❌ Модель <code>{model}</code> недоступна в вашем тарифе.\n\n"
                        f"🔄 Использую стандартную модель: <code>{DEFAULT_MODEL}</code>\n\n"
                        f"🔧 Используйте <code>/set_def_model имя_модели</code> для установки модели по умолчанию\n"
                        f"📋 Используйте <code>/available_models</code> для просмотра {tier_name} моделей",
                        parse_mode=ParseMode.HTML,
                    )
                    model = DEFAULT_MODEL

                model_info = onlysq_models["models"].get(model, {})
                can_stream = model_info.get("can-stream", False)
                notification = ""
                if not can_stream:
                    if model != DEFAULT_MODEL:
                        notification = f"⚠️ Модель <b>{model}</b> не поддерживает стриминг. Использую <b>{DEFAULT_MODEL}</b>\n"
                    model = DEFAULT_MODEL
                model_info = onlysq_models["models"].get(model, {})
                model_display_name = model_info.get("name", model)

                base_msg = await message.reply("🔄 Обработка...")
                try:
                    answer = ""
                    async for chunk in stream_text_api(
                        model=model,
                        messages=messages_for_ai,
                    ):
                        if chunk:
                            answer += chunk
                    if not answer:
                        await base_msg.edit_text("⚠️ Нет ответа от AI")
                        return
                    if model == "deepseek-r1":
                        answer = re.sub(
                            r"<think>.*?</think>", "", answer, flags=re.DOTALL
                        ).strip()
                    elif model.startswith("gemini"):
                        answer = re.sub(
                            r"<thought>.*?</thought>", "", answer, flags=re.DOTALL
                        ).strip()
                    raw_answer = (
                        f"{notification}"
                        f"💭 Запрос: {user_query}\n"
                        f"🧠 Модель: {model_display_name}\n\n"
                        f"📝 Ответ: {answer}"
                    )
                    chunks = [
                        raw_answer[i : i + 4096]
                        for i in range(0, len(raw_answer), 4096)
                    ]
                    for idx, chunk in enumerate(chunks):
                        if idx == 0:
                            await base_msg.edit_text(chunk)
                        else:
                            await message.answer(chunk)
                except Exception as e:
                    await base_msg.edit_text(f"❌ Ошибка: {e}")
                return

        if message.chat.type in ["channel", "private"]:
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
            answer = await simple_text_api(model=DEFAULT_MODEL, messages=messages)
            if not answer:
                await message.reply("⚠️ Нет ответа от AI")
            else:
                await message.reply(f"📝 Ответ: {answer}")
            return
        elif text_msg.startswith(
            ("http://", "https://")
        ) and await db.is_setting_enabled(chat_id, "autovideo"):
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
