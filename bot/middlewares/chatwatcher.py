import os
import logging
import traceback
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from bot import database

db = database.Database()


class ChatWatcher(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            bot: Bot = data["bot"]
            bot_username = (await bot.me()).username

            if isinstance(event, CallbackQuery):
                return await handler(event, data)

            if isinstance(event, Message):
                user = event.from_user
                chat = event.chat
                text = event.text or ""
                user_id = user.id
                chat_id = chat.id
                chat_type = chat.type
                chat_name = chat.full_name
                user_name = user.full_name
                language_code = user.language_code

                if not text:
                    return await handler(event, data)

                if not await db.chat_exists(chat_id):
                    await db.add_chat(chat_id, chat_data={"type": chat_type})
                    if chat_type != "private":
                        msg = f"🔔 Новый чат: {chat_id}, имя: {chat_name}"
                        logging.info(msg)
                        owner_id = os.getenv("OWNER_ID")
                        if owner_id:
                            await bot.send_message(owner_id, msg)

                if event.entities:
                    for entity in event.entities:
                        if entity.type == "bot_command":
                            command = text[
                                entity.offset : entity.offset + entity.length
                            ]
                            if "@" in command:
                                mentioned_bot = command.split("@")[1].lower()
                                if mentioned_bot != bot_username.lower():
                                    return await handler(event, data)

                if chat_type == "private" or text.startswith("/"):
                    user_info = await db.get_global_user(user_id)
                    if user_info is None:
                        await db.add_global_user(
                            user_id, {"language_code": language_code}
                        )
                        msg = f"🔔 Новый пользователь бота: {user_id}, имя: {user_name}"
                        logging.info(msg)
                        owner_id = os.getenv("OWNER_ID")
                        if owner_id:
                            await bot.send_message(owner_id, msg)

            return await handler(event, data)
        except Exception:
            logging.error("❌ Не удалось проверить чат.", exc_info=True)
            try:
                owner_id = os.getenv("OWNER_ID")
                if owner_id:
                    await bot.send_message(
                        owner_id,
                        f"❌ Не удалось проверить чат.\n\n📛 Traceback: {traceback.format_exc()}",
                    )
            except Exception:
                logging.error("❌ Не удалось отправить овнеру репорт.", exc_info=True)

            return await handler(event, data)
