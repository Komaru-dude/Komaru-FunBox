import os
import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot import logger
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
                        logger.info(msg)
                        if owner_id := os.getenv("OWNER_ID"):
                            await bot.send_message(owner_id, msg)
                            if chat.username:
                                link = f"https://t.me/{chat.username}"
                                await bot.send_message(owner_id, f"🔗 Ссылка: {link}")

                if chat_type == "private" or is_bot_command:
                    await db.log_command()
                    if not await db.user_exists(user_id, chat_id):
                        await db.add_user(user_id, chat_id)
                    if not await db.get_global_user(user_id):
                        await db.add_global_user(
                            user_id, {"language_code": language_code, "name": user_name}
                        )
                        msg = f'🔔 Новый пользователь бота: <a href="tg://user?id={user_id}">{user_id}</a>, имя: {user_name}'
                        logger.info(msg)
                        if owner_id := os.getenv("OWNER_ID"):
                            await bot.send_message(
                                owner_id, msg, parse_mode=ParseMode.HTML
                            )

            return await handler(event, data)
        except Exception:
            logger.error("❌ Ошибка в ChatWatcher:", exc_info=True)
            if owner_id := os.getenv("OWNER_ID"):
                await bot.send_message(
                    owner_id, f"❌ Ошибка в ChatWatcher:\n\n{traceback.format_exc()}"
                )
            return await handler(event, data)
