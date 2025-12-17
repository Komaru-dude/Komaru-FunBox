import os
import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot import logger
from bot.database.database import Database


class SpecificChat(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.restrict_enabled = os.getenv("SPECIFIC_CHAT", "").strip().lower() == "true"
        specific_chats = os.getenv("SPECIFIC_CHATS_ID", "")
        self.allowed_chat_ids = [
            int(cid.strip())
            for cid in specific_chats.split(",")
            if cid.strip().isdigit()
        ]
        self.owner_id = os.getenv("OWNER_ID")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            bot: Bot = data["bot"]
            db: Database = data["db"]

            if isinstance(event, CallbackQuery):
                return await handler(event, data)

            if isinstance(event, Message):
                chat_id = event.chat.id
                if self.restrict_enabled and self.allowed_chat_ids:
                    if chat_id not in self.allowed_chat_ids:
                        return None
                return await handler(event, data)

        except Exception:
            logger.error("❌ Ошибка в SpecificChat:", exc_info=True)
            if self.owner_id:
                await bot.send_message(
                    self.owner_id,
                    f"❌ Ошибка в SpecificChat:\n\n{traceback.format_exc()}",
                )
            return await handler(event, data)
