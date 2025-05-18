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
            event_type = data.get("event_update_type")
            bot: Bot = data["bot"]
            user_id = None
            chat_id = None

            if isinstance(event, Message):
                user_id = event.from_user.id
                chat_id = event.chat.id
                chat_name = event.chat.full_name
                chat_type = event.chat.type
            elif isinstance(event, CallbackQuery):
                return await handler(event, data)

            is_chat_init = await db.chat_exists(chat_id)

            if not is_chat_init:
                await db.add_chat(chat_id, chat_data={"type": chat_type})
                if chat_type == "private":
                    logging.info(
                        f"Новый пользователь бота: {chat_id}, имя: {chat_name}"
                    )
                    await bot.send_message(
                        os.getenv("OWNER_ID"),
                        f"🔔 Новый пользователь бота: {chat_id}, имя: {chat_name}",
                    )
                else:
                    logging.info(f"Новый чат: {chat_id}, имя: {chat_name}")
                    await bot.send_message(
                        os.getenv("OWNER_ID"),
                        f"🔔 Новый чат: {chat_id}, имя: {chat_name}",
                    )
            return await handler(event, data)
        except Exception:
            logging.error(
                f"❌ Не удалось проверить чат.\n\n📛 Traceback: {traceback.format_exc()}"
            )
            try:
                await bot.send_message(
                    os.getenv("OWNER_ID"),
                    f"❌ Не удалось проверить чат.\n\n📛 Traceback: {traceback.format_exc()}",
                )
            except Exception:
                logging.error(
                    f"❌ Не удалось отправить овнеру репорт, ошибка: {traceback.format_exc()}"
                )
            return await handler(event, data)
