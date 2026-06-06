from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database.database import Database
from bot.utils.aio_tools import convert_seconds


class CooldownFilter(BaseFilter):
    def __init__(self, command: str, cooldown: int, reduce_for_premium: bool = False, silent: bool = False):
        self.command = command
        self.cooldown = cooldown
        self.silent = silent
        self.reduce_for_premium = reduce_for_premium

    async def __call__(self, message: Message, db: Database):
        user_id = message.from_user.id
        chat_id = message.chat.id
        cooldown = self.cooldown

        if self.reduce_for_premium:
            is_premium = await db.is_premium_user(user_id)
            if is_premium:
                cooldown = self.cooldown // 2

        available = await db.is_command_available(user_id, self.command, cooldown)
        if not available:
            if not self.silent:
                if await db.is_setting_enabled(chat_id, "sendcooldown"):
                    cooldown_sec = await db.get_cooldown_remaining(
                        user_id, self.command
                    )
                    d, h, m, s = convert_seconds(cooldown_sec)
                    await message.reply(
                        f"⏳ Команда будет доступна через: {d} дней {h} часов {m} минут {s} секунд"
                    )
            return False
        return True
