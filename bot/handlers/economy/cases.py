import asyncio
import random
import traceback
from typing import cast

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import logger
from bot.database.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.keyboards.callback_data import CaseMenuCallback
from bot.keyboards.cases_keyboard import make_cases_kb
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import cases_config

cases_router = Router()


async def process_reward(user_id: int, db: Database, reward: str) -> str:
    split_reward = reward.split(":")

    if len(split_reward) != 2:
        logger.error("Неверный формат награды")
        return "❓ Неизвестный тип награды"

    reward_type = split_reward[0]
    reward_value = split_reward[1]

    if reward_type == "money":
        user_balance = cast(int, await db.get_global_user_param(user_id, "money"))
        new_balance = user_balance + int(reward_value)
        await db.set_global_user_param(user_id, "money", new_balance)
        return f"💰 Вы получили <b>{reward_value}</b> монет"
    elif reward_type == "premium":
        user_premium_expire = cast(
            int, await db.get_global_user_param(user_id, "premium_expire")
        )
        premium_days = int(reward_value) * 24 * 60 * 60
        new_premium_expire = user_premium_expire + int(premium_days)
        await db.set_global_user_param(user_id, "premium_expire", new_premium_expire)
        return f"💎 Вы получили <b>{reward_value}</b> дней премиума"
    else:
        return "❌ Ничего"


@cases_router.message(Command("cases"), CooldownFilter("cases", 15))
async def cmd_cases(message: Message, bot: Bot, db: Database, state: FSMContext):
    try:
        user_id = message.from_user.id  # type: ignore
        cases = cases_config["cases"]

        await message.reply(
            "🃏 Выберите кейс:", reply_markup=make_cases_kb(user_id, cases)
        )
    except Exception:
        await error_report(message, bot, "cases", traceback.format_exc())


@cases_router.callback_query(CaseMenuCallback.filter())
async def case_menu_callback(
    callback: CallbackQuery, callback_data: CaseMenuCallback, bot: Bot, db: Database
):
    try:
        user_id = callback_data.user_id
        case_id = callback_data.case_id
        case_info = next(
            (case for case in cases_config["cases"] if case["id"] == case_id), None
        )
        if not case_info:
            await callback.message.edit_text("📛 Не удалось найти кейс")
            return

        await callback.message.edit_text(
            f"⏳ <i>Открываем ваш {case_info['name']} кейс...</i>",
            parse_mode=ParseMode.HTML,
        )

        await asyncio.sleep(2.5)

        reward = random.choices(
            case_info["items"],
            weights=[reward["chance"] for reward in case_info["items"]],
            k=1,
        )
        reward_text = await process_reward(user_id, db, reward[0]["item_id"])
        await callback.message.edit_text(reward_text, parse_mode=ParseMode.HTML)
    except Exception:
        await error_report(callback.message, bot, "cases", traceback.format_exc())
