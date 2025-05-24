import random
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from bot import database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.utils.aio_tools import error_report

eco_router = Router()
db = database.Database()


@eco_router.message(
    Command("work"),
    FuncEnabled(func_name="economy"),
    CooldownFilter(command="work", cooldown=14400),
)
async def cmd_work(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    chat_data = await db.get_chat(chat_id)
    current_bal = await db.get_user_param(user_id, chat_id, "money")

    min_income = chat_data["min_work_income"]
    max_income = chat_data["max_work_income"]
    current_income = random.randint(min_income, max_income)

    new_bal = current_bal + current_income
    await db.set_user_param(user_id, chat_id, "money", new_bal)
    await message.reply(
        f"👨‍💻 Вы заработали: {current_income}\n{chat_data["currency_sign"]} Ваш новый баланс: {new_bal}"
    )
