from aiogram.filters import BaseFilter
from aiogram.types import Message

from bot.database.database import Database


class PremiumFilter(BaseFilter):
    async def __call__(self, message: Message, db: Database):
        user_id = message.from_user.id
        is_premium = await db.is_premium_user(user_id)
        if not is_premium:
            await message.reply(
                "🚀 Эта команда доступна только для премиум пользователей"
            )
            return False
        return True
