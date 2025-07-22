from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database import Database


class FuncEnabled(BaseFilter):
    def __init__(self, func_name: str):
        self.func_name = func_name

    async def __call__(self, message: Message, db: Database) -> bool:
        chat_id = message.chat.id
        enabled = await db.is_setting_enabled(chat_id, self.func_name)
        if not enabled:
            if await db.is_setting_enabled(chat_id, "senddisabledmsg"):
                await message.reply("❌ Функция отключена")
            return False
        return True
