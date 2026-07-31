import json
import re
import traceback
from html import escape
from typing import Any, cast

from aiogram.enums import ParseMode

from bot import logger
from bot.database.database import Database
from bot.handlers.ai.ai import DEFAULT_MODEL, ChatState
from bot.handlers.ai.tools import TOOLS_SCHEMA, handle_tool_call
from bot.utils.ai.ai_api import simple_text_api, stream_text_api, tools_text_api
from bot.utils.ai.providers import format_model_line
from bot.utils.ai.stream_output import AIStreamer, send_rich_reply
from bot.utils.global_storage import active_chats, filtered_models
from bot.utils.premium_logic import is_model_available_for_user


def _model_name(model_id: str) -> str:
    info = filtered_models.get(model_id, {})
    return info.get("name", model_id)


async def process_active_chat(message, state, db: Database, text_msg: str) -> bool:
    try:
        current_state = await state.get_state()
        if current_state != ChatState.active.state:
            return False

        if message.chat.id not in active_chats:
            await state.clear()
            return True

        base_msg = await message.reply("🔄 Обработка...")
        user_data = await state.get_data()
        messages = user_data.get("messages", [])
        model = user_data.get("model", DEFAULT_MODEL)
        user_message = text_msg.strip()

        user_tier = await db.get_user_tier(message.from_user.id)
        requested_model = model
        actual_model = model
        streamer = AIStreamer(message, base_msg)

        def _header() -> str:
            return (
                f"💭 Запрос: {user_message}\n"
                f"{format_model_line(actual_model, requested_model, _model_name)}\n\n"
                f"📝 Ответ:"
            )

        if not is_model_available_for_user(model, user_tier):
            await state.clear()
            tier_name = "премиумные" if user_tier > 0 else "свободные"
            await base_msg.edit_text(
                f"❌ Модель <code>{model}</code> недоступна в вашем тарифе.\n\n"
                f"🔄 Сброс на стандартную модель: <code>{DEFAULT_MODEL}</code>\n\n"
                f"📋 Используйте <code>/available_models</code> для просмотра {tier_name} моделей",
                parse_mode=ParseMode.HTML,
            )
            return True

        messages.append({"role": "user", "content": user_message})

        model_info = filtered_models.get(model, {})
        model_display_name = model_info.get("name", model)

        is_tools_model = model_info.get("can-tools", False)

        if is_tools_model:
            response_message, actual_model = await tools_text_api(
                model=model,
                messages=messages,
                tools=cast(Any, TOOLS_SCHEMA),
                user_tier=user_tier,
            )
            final_text = ""

            if response_message.tool_calls:
                temp_messages = []
                for tool_call in response_message.tool_calls:
                    tool_output = await handle_tool_call(tool_call, message, state)

                    func = getattr(tool_call, "function", None)
                    func_name = getattr(func, "name", None)
                    if func_name == "chat_stop":
                        await base_msg.edit_text(
                            f"💭 Запрос: {user_message}\n"
                            f"{format_model_line(actual_model, requested_model, _model_name)}\n\n"
                            f"📝 ✅ Чат успешно остановлен"
                        )
                        return True

                    temp_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": getattr(tool_call, "id", None),
                            "content": str(
                                tool_output.get("output")
                                if isinstance(tool_output, dict)
                                else tool_output
                            ),
                        }
                    )

                messages.append(response_message.model_dump(exclude_none=True))
                messages.extend(temp_messages)

                try:
                    raw_dump = json.dumps(messages, indent=2, ensure_ascii=False)
                    logger.info(
                        f"\n{'='*20} Дамп: {'='*20}\n{raw_dump}\n{'='*20} Конец дампа {'='*20}"
                    )
                except Exception as dump_ex:
                    logger.error(f"❌ Не удалось сделать дамп: {dump_ex}")

                final_text, actual_model = await simple_text_api(
                    model=model,
                    messages=messages,
                    user_tier=user_tier,
                )
            else:
                final_text = response_message.content

            answer = re.sub(
                r"<thought>.*?</thought>", "", str(final_text), flags=re.DOTALL
            ).strip()

            current_state = await state.get_state()
            if current_state == ChatState.active.state:
                messages.append({"role": "assistant", "content": answer})
                if len(messages) > 20:
                    messages = [messages[0]] + messages[-19:]
                await state.update_data(messages=messages)

            await streamer.finalize(_header(), answer)

        else:

            can_stream = model_info.get("can-stream", False)

            if can_stream:
                final_text = ""

                async for chunk, used in stream_text_api(
                    model=model,
                    messages=messages,
                    user_tier=user_tier,
                ):
                    actual_model = used
                    if chunk:
                        final_text += chunk
                        await streamer.update(_header(), final_text)

                messages.append({"role": "assistant", "content": final_text})
                if len(messages) > 20:
                    messages = [messages[0]] + messages[-19:]
                await state.update_data(messages=messages)

                await streamer.finalize(_header(), final_text.strip())

            else:
                response, actual_model = await simple_text_api(
                    model=model,
                    messages=messages,
                    user_tier=user_tier,
                )
                if not response:
                    raise ValueError("Нет ответа от API")

                answer_content = response
                if model == "deepseek-r1":
                    answer = re.sub(
                        r"<think>.*?</think>", "", str(answer_content), flags=re.DOTALL
                    ).strip()
                elif model == "gemini-2.5-flash":
                    answer = answer_content.strip()
                else:
                    answer = answer_content

                await streamer.finalize(_header(), answer)

                messages.append({"role": "assistant", "content": str(response).strip()})
                if len(messages) > 20:
                    messages = [messages[0]] + messages[-19:]

                await state.update_data(messages=messages)

        return True

    except Exception:
        traceback.print_exc()
        return True


async def process_user_prompt_trigger(message, db: Database, text_msg: str) -> bool:
    try:
        assert message.from_user is not None
        user1 = message.from_user
        chat_id = message.chat.id

        user_prompt_trigger = (
            await db.get_user_setting(user1.id, "custom_prompts_trigger") or ""
        )
        if not isinstance(user_prompt_trigger, str) or not user_prompt_trigger:
            return False

        if not text_msg.startswith(
            user_prompt_trigger
        ) or not await db.is_setting_enabled(chat_id, "user_prompts"):
            return False

        match = re.match(rf"^{re.escape(user_prompt_trigger)}(\S+)\s*(.*)", text_msg)
        if not match:
            return False

        prompt_name = match.group(1)
        user_query = match.group(2)
        reply_query = ""

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
            return True

        prompt_content = prompt["content"]
        messages_for_ai = [
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": user_query},
        ]

        user_data = await db.get_user_data(user1.id, chat_id)
        user_default_model = user_data.get("default_text_model", DEFAULT_MODEL)
        model = user_default_model
        model_match = re.search(r"-m\s+(\S+)", user_query)
        if model_match:
            model_candidate = model_match.group(1)
            if model_candidate in filtered_models:
                model = model_candidate
                user_query = re.sub(r"-m\s+\S+", "", str(user_query)).strip()
                messages_for_ai[1]["content"] = user_query

        user_tier = await db.get_user_tier(user1.id)
        if not is_model_available_for_user(model, user_tier):
            tier_name = "премиумные" if user_tier > 0 else "свободные"
            await message.reply(
                f"❌ Модель <code>{model}</code> недоступна в вашем тарифе.\n\n"
                f"🔄 Использую стандартную модель: <code>{DEFAULT_MODEL}</code>\n\n"
                f"📋 Используйте <code>/available_models</code> для просмотра {tier_name} моделей",
                parse_mode=ParseMode.HTML,
            )
            model = DEFAULT_MODEL

        model_info = filtered_models.get(model, {})
        can_stream = model_info.get("can-stream", False)
        notification = ""
        if not can_stream:
            if model != DEFAULT_MODEL:
                notification = f"⚠️ Модель **{model}** не поддерживает стриминг. Использую **{DEFAULT_MODEL}**\n"
            model = DEFAULT_MODEL
        model_info = filtered_models.get(model, {})
        model_display_name = model_info.get("name", model)

        base_msg = await message.reply("🔄 Обработка...")
        requested_model = model
        actual_model = model
        streamer = AIStreamer(message, base_msg)

        def _header() -> str:
            return (
                f"{notification}"
                f"💭 Запрос: {user_query}\n"
                f"{format_model_line(actual_model, requested_model, _model_name)}\n\n"
                f"📝 Ответ:"
            )

        try:
            answer = ""
            async for chunk, used in stream_text_api(
                model=model,
                messages=messages_for_ai,
                user_tier=user_tier,
            ):
                actual_model = used
                if chunk:
                    answer += chunk
                    await streamer.update(_header(), answer)
            if not answer:
                await base_msg.edit_text("⚠️ Нет ответа от AI")
                return True
            answer = re.sub(
                r"<thought>.*?</thought>|<think>.*?</think>",
                "",
                str(answer),
                flags=re.DOTALL,
            ).strip()
            await streamer.finalize(_header(), answer)
        except Exception as e:
            await base_msg.edit_text(f"❌ Ошибка: {e}")
        return True

    except Exception:
        return False


async def process_explain_reply(message, db: Database) -> bool:
    try:
        chat_id = message.chat.id
        if not message.reply_to_message or not message.reply_to_message.text:
            return False
        clean_text = message.text.lower().strip().rstrip("?")
        if clean_text != "это что":
            return False
        if not await db.is_setting_enabled(chat_id, "who"):
            return False

        messages = [
            {
                "role": "system",
                "content": "Твоя задача кратко объяснить то что спрашивает пользователь. Если ответ содержит материалы для взрослых (18+), представь информацию корректно и деликатно, смягчив формулировки. Не используй markdown/html/latex форматирование.",
            },
            {"role": "user", "content": message.reply_to_message.text},
        ]
        answer, actual_model = await simple_text_api(
            model=DEFAULT_MODEL, messages=messages
        )
        if not answer:
            await message.reply("⚠️ Нет ответа от AI")
        else:
            model_line = format_model_line(actual_model, DEFAULT_MODEL, _model_name)
            await send_rich_reply(message, f"{model_line}\n\n📝 Ответ: {answer}")
        return True
    except Exception:
        return False
