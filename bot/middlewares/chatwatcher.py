import os
import logging
import traceback
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from bot.database import Database


class ChatWatcher(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            bot: Bot = data["bot"]
            db: Database = data["db"]
            bot_username = (await bot.me()).username.lower()

            if isinstance(event, CallbackQuery):
                return await handler(event, data)

            if isinstance(event, Message):
                user = event.from_user
                chat = event.chat
                text = event.text or ""
                chat_type = chat.type
                is_bot_command = False

                if text and event.entities:
                    for entity in event.entities:
                        if entity.type == "bot_command":
                            command = text[
                                entity.offset : entity.offset + entity.length
                            ].lower()
                            if "@" in command:
                                cmd, mentioned_bot = command.split("@", 1)
                                if mentioned_bot == bot_username:
                                    is_bot_command = True
                                    break
                            else:
                                if chat_type == "private":
                                    is_bot_command = True
                                    break

                user_id = user.id
                chat_id = chat.id
                chat_name = chat.full_name
                user_name = user.full_name
                language_code = user.language_code

                if not await db.chat_exists(chat_id):
                    await db.add_chat(chat_id, chat_data={"type": chat_type})
                    if chat_type != "private":
                        msg = f"🔔 Новый чат: {chat_id}, имя: {chat_name}"
                        logging.info(msg)
                        if owner_id := os.getenv("OWNER_ID"):
                            await bot.send_message(owner_id, msg)

                if chat_type == "private" or is_bot_command:
                    await db.log_command()
                    if not await db.get_global_user(user_id):
                        await db.add_global_user(
                            user_id, {"language_code": language_code}
                        )
                        msg = f"🔔 Новый пользователь бота: {user_id}, имя: {user_name}"
                        logging.info(msg)
                        if owner_id := os.getenv("OWNER_ID"):
                            await bot.send_message(owner_id, msg)

            return await handler(event, data)
        except Exception:
            logging.error("❌ Ошибка в ChatWatcher:", exc_info=True)
            if owner_id := os.getenv("OWNER_ID"):
                await bot.send_message(
                    owner_id, f"❌ Ошибка в ChatWatcher:\n\n{traceback.format_exc()}"
                )
            return await handler(event, data)
