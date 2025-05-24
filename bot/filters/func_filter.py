import logging
from aiogram.filters import BaseFilter
from aiogram.types import Message
from bot import database

db = database.Database()


class FuncEnabled(BaseFilter):
    def __init__(self, func_name: str):
        self.func_name = func_name

    async def __call__(self, message: Message) -> bool:
        chat_id = message.chat.id
        enabled = await db.is_feature_enabled(chat_id, self.func_name)
        logging.info(enabled)
        if not enabled:
            if await db.is_feature_enabled(chat_id, "senddisabledmsg"):
                await message.reply("❌ Функция отключена")
            return False
