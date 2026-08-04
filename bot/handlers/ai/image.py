import base64
import re
import traceback
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message

from bot.database.database import Database
from bot.handlers.ai.ai import DEFAULT_MODEL
from bot.utils.ai.ai_api import stream_text_api
from bot.utils.ai.providers import format_model_line
from bot.utils.ai.stream_output import AIStreamer
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import filtered_models
from bot.utils.premium_logic import is_model_available_for_user


image_router = Router()


@image_router.message(F.photo)
async def handle_prompt_with_image(message: Message, bot: Bot, db: Database) -> None:
    """Обработка кастомных промптов с изображениями."""
    try:
        assert message.from_user is not None
        user1 = message.from_user
        chat_id = message.chat.id

        if not await db.is_setting_enabled(chat_id, "user_prompts"):
            return

        user_prompt_trigger = (
            await db.get_user_setting(user1.id, "custom_prompts_trigger") or "!"
        )

        caption = message.caption or ""
        if not caption.startswith(user_prompt_trigger):
            return

        match = re.match(rf"^{re.escape(user_prompt_trigger)}(\S+)\s*(.*)", caption)
        if not match:
            return

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

        user_data = await db.get_user_data(user1.id, chat_id)
        user_default_model = user_data.get("default_text_model", DEFAULT_MODEL)
        model = user_default_model

        model_match = re.search(r"-m\s+(\S+)", user_query)
        if model_match:
            model_candidate = model_match.group(1)
            if model_candidate in filtered_models:
                model = model_candidate
                user_query = re.sub(r"-m\s+\S+", "", user_query).strip()

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

        # Обработка изображения
        is_tools_model = model_info.get("can-tools", False)
        if not is_tools_model:
            await base_msg.edit_text(
                f"❌ Модель <b>{model_display_name}</b> не поддерживает обработку изображений. "
                f"Используйте модель с поддержкой vision.",
                parse_mode=ParseMode.HTML,
            )
            return

        if not message.photo:
            await message.reply("📛 Не удалось обработать фото")
            return

        try:
            await base_msg.edit_text("🔄 Обнаружено фото, обрабатываю...")
            photo = message.photo[-1]
            file = await bot.get_file(photo.file_id)
            assert file.file_path is not None, "Telegram не вернул путь к файлу"
            file_bytes = await bot.download_file(file.file_path)

            if file.file_path.endswith(".png"):
                mime_type = "image/png"
            elif file.file_path.endswith(".webp"):
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            assert file_bytes is not None, "Файл не был загружен"
            base64_image = base64.b64encode(file_bytes.read()).decode("utf-8")

            messages_for_ai = [
                {"role": "system", "content": prompt_content},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_query or "Что на картинке?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                },
            ]

            await base_msg.edit_text("🔄 Обработка...")
        except Exception as e:
            await base_msg.edit_text(f"⚠️ Не удалось обработать изображение: {e}")
            return

        try:
            answer = ""
            requested_model = model
            actual_model = model
            streamer = AIStreamer(message, base_msg)

            def _header() -> str:
                return (
                    f"{notification}"
                    f"💭 Запрос: {user_query or 'Анализ изображения'}\n"
                    f"{format_model_line(actual_model, requested_model)}\n\n"
                    f"📝 Ответ:"
                )

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
                return

            answer = re.sub(
                r"<thought>.*?</thought>|<think>.*?</think>",
                "",
                answer,
                flags=re.DOTALL,
            ).strip()

            await streamer.finalize(_header(), answer)
        except Exception as e:
            await base_msg.edit_text(f"❌ Ошибка: {e}")

    except Exception:
        await error_report(
            message, bot, "handle_prompt_with_image", traceback.format_exc()
        )
