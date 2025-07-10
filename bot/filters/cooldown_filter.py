from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database import Database
from bot.utils.aio_tools import convert_seconds


class CooldownFilter(BaseFilter):
    def __init__(self, command: str, cooldown: int):
        self.command = command
        self.cooldown = cooldown

    async def __call__(self, message: Message, db: Database):
        user_id = message.from_user.id
        chat_id = message.chat.id
        available = await db.is_command_available(user_id, self.command, self.cooldown)
        if not available:
            if await db.is_feature_enabled(chat_id, "sendcooldown"):
                cooldown_sec = await db.get_cooldown_remaining(user_id, self.command)
                d, h, m, s = convert_seconds(cooldown_sec)
                await message.reply(
                    f"⏳ Команда будет доступна через: {d} дней {h} часов {m} минут {s} секунд"
                )
            return False
        return True
