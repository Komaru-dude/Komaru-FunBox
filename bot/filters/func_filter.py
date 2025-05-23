from aiogram.filters import BaseFilter
from aiogram.types import Message
from bot import database

db = database.Database()


class func_enabled(BaseFilter):
    def __init__(self, func_name: str):
        self.func_name = func_name

    async def __call__(self, message: Message) -> bool:
        chat_id = message.chat.id
        return await db.is_feature_enabled(chat_id, self.func_name)
