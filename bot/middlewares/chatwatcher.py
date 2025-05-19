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

            if isinstance(event, CallbackQuery):
                return await handler(event, data)

            if isinstance(event, Message):
                user_id = event.from_user.id
                chat_id = event.chat.id
                chat_type = event.chat.type
                chat_name = event.chat.full_name
                language_code = event.from_user.language_code
                text = event.text or ""

                is_chat_init = await db.chat_exists(chat_id)
                if not is_chat_init:
                    await db.add_chat(chat_id, chat_data={"type": chat_type})
                    msg = (
                        f"🔔 Новый пользователь бота: {chat_id}, имя: {chat_name}"
                        if chat_type == "private"
                        else f"🔔 Новый чат: {chat_id}, имя: {chat_name}"
                    )
                    logging.info(msg)
                    owner_id = os.getenv("OWNER_ID")
                    if owner_id:
                        await bot.send_message(owner_id, msg)

                if chat_type == "private" or text.startswith("/"):
                    user_info = await db.get_global_user(user_id)
                    if user_info is None:
                        await db.add_global_user(
                            user_id, {"language_code": language_code}
                        )
                        msg = f"🔔 Новый пользователь бота: {chat_id}, имя: {chat_name}"
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
