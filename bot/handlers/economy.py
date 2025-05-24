import random
import traceback
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from bot.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.filters.chat_type import ChatTypeFilter
from bot.utils.aio_tools import error_report

eco_router = Router()


@eco_router.message(
    Command("work"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    FuncEnabled(func_name="economy"),
    CooldownFilter(command="work", cooldown=14400),
)
async def cmd_work(message: Message, bot: Bot, db: Database):
    try:
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
    except Exception:
        await error_report(message, bot, "work", traceback.format_ext())


@eco_router.message(
    Command("steal"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    FuncEnabled(func_name="economy"),
    CooldownFilter(command="steal", cooldown=14400),
)
async def cmd_steal(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        chat_data = await db.get_chat(chat_id)
        current_bal = await db.get_user_param(user_id, chat_id, "money")
        if current_bal < chat_data["max_steal_penalty"] / 2:
            await message.reply(f"❌ Вам нужно иметь на балансе хотя бы половину от максимальной суммы штрафа ({chat_data["currency_sign"]}{chat_data['max_steal_penalty'] / 2})")
            return

        min_income = chat_data["min_steal_income"]
        max_income = chat_data["max_steal_income"]
        current_income = random.randint(min_income, max_income)

        min_penalty = chat_data["min_steal_penalty"]
        max_penalty = chat_data["max_steal_penalty"]
        current_penalty = random.randint(min_penalty, max_penalty)

        fail_percent = chat_data["steal_fail_percent"]
        if random.randint(1, 100) <= fail_percent:
            new_bal = current_bal - current_penalty
            await message.reply(
                f"😔 Вам не повезло.\n🧨 Вы потеряли: {current_penalty}\n{chat_data["currency_sign"]} Ваш новый баланс: {new_bal}"
            )
        else:
            new_bal = current_bal + current_income
            await message.reply(
                f"🤑 Повезло!\n💡 Вы заработали: {current_income}\n{chat_data["currency_sign"]} Ваш новый баланс: {new_bal}"
            )

        await db.set_user_param(user_id, chat_id, "money", new_bal)

    except Exception:
        await error_report(message, bot, "steal", traceback.format_ext())
