from typing import Union

from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database.database import Database


class ChatTypeFilter(BaseFilter):
    def __init__(self, chat_type: Union[str, list]):
        self.chat_type = chat_type

    async def __call__(self, message: Message, db: Database) -> bool:
        chat_type = message.chat.type
        if isinstance(self.chat_type, str):
            allowed = chat_type == self.chat_type
            allowed_types = [self.chat_type]
        else:
            allowed = chat_type in self.chat_type
            allowed_types = self.chat_type

        if allowed:
            return True
        else:
            if await db.is_setting_enabled(message.chat.id, "senddisabledmsg"):
                if len(allowed_types) == 1:
                    await message.reply(
                        f"❌ Эту команду можно использовать только в чатах типа: {allowed_types[0]}."
                    )
                else:
                    types_list = ", ".join(allowed_types)
                    await message.reply(
                        f"❌ Эту команду можно использовать только в чатах следующих типов: {types_list}."
                    )
            return False
