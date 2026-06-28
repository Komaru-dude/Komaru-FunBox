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
from bot.keyboards.cases_keyboard import make_case_detail_kb, make_cases_kb
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import cases_config

cases_router = Router()


def format_reward(reward: str) -> str:
    split_reward = reward.split(":")

    if len(split_reward) != 2:
        logger.error("Неверный формат награды")
        return "❓ Неизвестный тип награды"

    reward_type, reward_value = split_reward

    if reward_type == "money":
        return f"💰 Вы получили <b>{reward_value}</b> монет"
    elif reward_type == "premium":
        return f"💎 Вы получили <b>{reward_value}</b> дней премиума"
    else:
        return "❌ Ничего"


async def apply_rewards(
    user_id: int, db: Database, rewards: list[str]
) -> dict[str, int]:
    totals: dict[str, int] = {}
    for reward in rewards:
        split_reward = reward.split(":")
        if len(split_reward) != 2:
            continue
        reward_type, reward_value = split_reward
        totals[reward_type] = totals.get(reward_type, 0) + int(reward_value)

    if totals.get("money"):
        balance = cast(int, await db.get_global_user_param(user_id, "money"))
        await db.set_global_user_param(user_id, "money", balance + totals["money"])
    if totals.get("premium"):
        expire = cast(int, await db.get_global_user_param(user_id, "premium_expire"))
        await db.set_global_user_param(
            user_id, "premium_expire", expire + totals["premium"] * 24 * 60 * 60
        )
    return totals


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
        count = callback_data.count
        action = callback_data.action

        if action == "back":
            await callback.message.edit_text(
                "🃏 Выберите кейс:",
                reply_markup=make_cases_kb(user_id, cases_config["cases"]),
            )
            return

        case_info = next(
            (case for case in cases_config["cases"] if case["id"] == case_id), None
        )
        if not case_info:
            await callback.message.edit_text("📛 Не удалось найти кейс")
            return

        if action == "menu":
            items_list = "\n".join(f"• {item['name']}" for item in case_info["items"])
            text = (
                f"🃏 <b>{case_info['name']}</b>\n"
                f"{case_info['description']}\n"
                f"🪙 Цена: <b>{case_info['price']}</b> монет\n"
                f"📦 <b>Возможные награды:</b>\n{items_list}"
            )
            await callback.message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=make_case_detail_kb(user_id, case_info),
            )
            return

        price = case_info["price"] * count
        balance = cast(int, await db.get_global_user_param(user_id, "money"))
        if balance < price:
            await callback.answer(
                f"❌ Недостаточно монет: нужно {price}, у вас {balance}",
                show_alert=True,
            )
            return
        await db.set_global_user_param(user_id, "money", balance - price)

        await callback.message.edit_text(
            f"⏳ <i>Открываем ваш {case_info['name']} кейс x{count}...</i>",
            parse_mode=ParseMode.HTML,
        )

        rewards = random.choices(
            case_info["items"],
            weights=[reward["chance"] for reward in case_info["items"]],
            k=count,
        )
        reward_ids = [reward["item_id"] for reward in rewards]

        reward_lines: list[str] = []
        for i, item_id in enumerate(reward_ids, 1):
            await asyncio.sleep(2.5)
            reward_lines.append(f"{i}. {format_reward(item_id)}")
            text = "\n".join(reward_lines)
            if i < count:
                text += f"\n\n⏳ <i>Открываем {i + 1}/{count}...</i>"
            await callback.message.edit_text(text, parse_mode=ParseMode.HTML)

        totals = await apply_rewards(user_id, db, reward_ids)

        summary_parts = []
        if totals.get("money"):
            summary_parts.append(f"💰 <b>{totals['money']}</b> монет")
        if totals.get("premium"):
            summary_parts.append(f"💎 <b>{totals['premium']}</b> дней премиума")
        summary = (
            "🎁 <b>Итого:</b> " + ", ".join(summary_parts)
            if summary_parts
            else "🎁 <b>Итого:</b> ничего"
        )

        await callback.message.edit_text(
            "\n".join(reward_lines) + "\n\n" + summary,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(callback.message, bot, "cases", traceback.format_exc())
