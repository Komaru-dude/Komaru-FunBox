import time
from aiogram.filters import BaseFilter
from aiogram.types import Message
from bot import database

db = database.Database()

class CooldownFilter(BaseFilter):
    def __init__(self, command: str, cooldown: int):
        self.command = command
        self.cooldown = cooldown

    async def __call__(self, message: Message):
        user_id = message.from_user.id
        chat_id = message.chat.id
        cooldown = await db.is_command_available(user_id, chat_id, self.command, self.cooldown)
        if not cooldown:
            if await db.is_feature_enabled(chat_id, "sendcooldown"):
                cooldown_sec = await db.get_cooldown_remaining(user_id, chat_id, self.command)
                await message.reply(f"⏳ Команда будет доступна через: {cooldown_sec}")
            return False
        else:
            return True