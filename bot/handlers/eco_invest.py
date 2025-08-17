import json
import traceback

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.keyboards.callback_data import InvestMenuCallback
from bot.keyboards.invest_keyboard import (
    load_stocks,
    make_menu_kb,
    make_portfolio_kb,
    make_stocks_kb,
)
from bot.utils.aio_tools import error_report

invest_router = Router()


@invest_router.message(
    Command("invest_menu"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    CooldownFilter("invest_menu", 300),
    FuncEnabled("economy"),
)
async def cmd_invest_menu(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        await message.reply(
            f"👋 Привет, {message.from_user.first_name}, выбери опцию ниже для продолжения",
            reply_markup=make_menu_kb(user_id),
        )
    except Exception:
        await error_report(message, bot, "invest_menu", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "buy_stock"))
async def cb_show_stocks(
    callback: CallbackQuery, bot: Bot, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        await callback.message.edit_text(
            "📈 Доступные акции для покупки:", reply_markup=make_stocks_kb(user_id)
        )
    except Exception:
        await error_report(callback.message, bot, "buy_stock", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "buy_stock_item"))
async def cb_buy_stock_item(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        stock_id = callback_data.stock_id
        stocks = load_stocks()
        stock = stocks.get(str(stock_id))

        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return

        if not stock:
            await callback.answer("❌ Акция не найдена", show_alert=True)
            return

        user_bal = await db.get_global_user_param(user_id, "money")
        price = stock["price"]

        if user_bal < price:
            await callback.answer("💸 Недостаточно денег", show_alert=True)
            return

        await db.set_global_user_param(user_id, "money", user_bal - price)

        items_raw = await db.get_global_user_param(user_id, "items") or "[]"
        try:
            items = json.loads(items_raw)
        except Exception:
            items = []

        items.append({"type": "stock", "id": stock_id, "price": price})

        await db.set_global_user_param(user_id, "items", json.dumps(items))

        await callback.answer(
            f"✅ Куплено: {stock['name']} за {price}$", show_alert=True
        )

    except Exception:
        await error_report(
            callback.message, bot, "buy_stock_item", traceback.format_exc()
        )


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "sell_stock"))
async def cb_sell_stock(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id

        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return

        items_raw = await db.get_global_user_param(user_id, "items") or "[]"
        try:
            items = json.loads(items_raw)
        except Exception:
            items = []

        stocks = [i for i in items if i.get("type") == "stock"]

        if not stocks:
            await callback.answer("📭 У вас нет акций", show_alert=True)
            return

        market = load_stocks()
        text = "📤 Ваши акции для продажи:\n"
        for s in stocks:
            stock_info = market.get(str(s["id"]))
            if stock_info:
                text += (
                    f"- {stock_info['name']} "
                    f"(куплено за {s['price']}$, текущая цена {stock_info['price']}$)\n"
                )

        await callback.message.edit_text(text)

    except Exception:
        await error_report(callback.message, bot, "sell_stock", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "my_portfolio"))
async def cb_my_portfolio(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id

        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return

        items_raw = await db.get_global_user_param(user_id, "items") or "[]"
        try:
            items = json.loads(items_raw)
        except Exception:
            items = []

        stocks = [i for i in items if i.get("type") == "stock"]

        if not stocks:
            await callback.answer("📭 Портфель пуст", show_alert=True)
            return

        market = load_stocks()
        total_value = 0
        text = "💼 Ваш портфель:\n"
        for s in stocks:
            stock_info = market.get(str(s["id"]))
            if stock_info:
                value = stock_info["price"]
                total_value += value
                text += f"- {stock_info['name']}: {value}$ (куплено за {s['price']}$)\n"

        text += f"\n💰 Общая стоимость: {total_value}$"
        await callback.message.edit_text(text, reply_markup=make_portfolio_kb(user_id))

    except Exception:
        await error_report(
            callback.message, bot, "my_portfolio", traceback.format_exc()
        )


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "back_to_menu"))
async def cb_switch_to_menu(
    callback: CallbackQuery, bot: Bot, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id

        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return

        await callback.message.edit_text(
            f"👋 Привет, {callback.from_user.first_name}, выбери опцию ниже для продолжения",
            reply_markup=make_menu_kb(user_id),
        )
    except Exception:
        await error_report(callback.message, bot, "invest_menu", traceback.format_exc())
