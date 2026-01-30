import traceback

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ForceReply, Message

from bot.database.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.keyboards.callback_data import InvestMenuCallback
from bot.keyboards.invest_keyboard import (
    load_stocks,
    make_buy_options_kb,
    make_menu_kb,
    make_portfolio_kb,
    make_sell_options_kb,
    make_sell_stocks_kb,
    make_stocks_kb,
)
from bot.utils.aio_tools import error_report

invest_router = Router()


class AskQty(StatesGroup):
    waiting_qty = State()


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
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        stock_id = callback_data.stock_id
        stocks = load_stocks()
        stock = stocks.get(str(stock_id))
        stock_price = round(stock["price"], 2)
        if not stock:
            await callback.answer("❌ Акция не найдена", show_alert=True)
            return
        user_bal = await db.get_global_user_param(user_id, "money") or 0
        kb = make_buy_options_kb(user_id, stock_id, stock_price, 2), user_bal)
        await callback.message.edit_text(
            f"📈 {stock['name']} — {stock_price}$\nВыберите опцию:", reply_markup=kb
        )
    except Exception:
        await error_report(
            callback.message, bot, "buy_stock_item", traceback.format_exc()
        )


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "quick_buy"))
async def cb_quick_buy(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        stock_id = callback_data.stock_id
        qty = int(callback_data.qty or 1)
        stocks = load_stocks()
        stock = stocks.get(str(stock_id))
        if not stock:
            await callback.answer("❌ Акция не найдена", show_alert=True)
            return
        price = stock["price"]
        user_bal = await db.get_global_user_param(user_id, "money") or 0
        total_cost = round(price * qty, 2)
        if user_bal < total_cost:
            await callback.answer("💸 Недостаточно денег", show_alert=True)
            return
        await db.set_global_user_param(user_id, "money", user_bal - total_cost)
        items = await db.get_global_user_param(user_id, "items") or []
        if not isinstance(items, list):
            items = []
        for _ in range(qty):
            items.append({"type": "stock", "id": stock_id, "price": round(price, 2)
        await db.set_global_user_param(user_id, "items", items)
        await callback.answer(
            f"✅ Куплено: {stock['name']} x{qty} за {total_cost}$", show_alert=True
        )
        await callback.message.edit_text(
            f"👋 Привет, {callback.from_user.first_name}, выбери опцию ниже для продолжения",
            reply_markup=make_menu_kb(user_id),
        )
    except Exception:
        await error_report(callback.message, bot, "quick_buy", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "ask_buy_qty"))
async def cb_ask_buy_qty(
    callback: CallbackQuery,
    bot: Bot,
    callback_data: InvestMenuCallback,
    state: FSMContext,
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        stock_id = callback_data.stock_id
        stocks = load_stocks()
        stock = stocks.get(str(stock_id))
        if not stock:
            await callback.answer("❌ Акция не найдена", show_alert=True)
            return
        await state.update_data(action="buy", user_id=user_id, stock_id=stock_id)
        await callback.message.answer(
            f"Введите количество акций {stock['name']} для покупки (целое число):",
            reply_markup=ForceReply(selective=True),
        )
        await state.set_state(AskQty.waiting_qty)
        await callback.answer()
    except Exception:
        await error_report(callback.message, bot, "ask_buy_qty", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "sell_stock"))
async def cb_sell_stock(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        items = await db.get_global_user_param(user_id, "items") or []
        user_stocks = [i for i in items if i.get("type") == "stock"]
        if not user_stocks:
            await callback.answer("📭 У вас нет акций", show_alert=True)
            return
        market = load_stocks()
        kb = make_sell_stocks_kb(user_id, user_stocks, market)
        await callback.message.edit_text(
            "📤 Выберите акцию для продажи:", reply_markup=kb
        )
    except Exception:
        await error_report(callback.message, bot, "sell_stock", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "sell_stock_item"))
async def cb_sell_stock_item(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        stock_id = str(callback_data.stock_id)
        items = await db.get_global_user_param(user_id, "items") or []
        user_stocks = [
            i
            for i in items
            if i.get("type") == "stock" and str(i.get("id")) == stock_id
        ]
        if not user_stocks:
            await callback.answer("📭 У вас нет этой акции", show_alert=True)
            return
        market = load_stocks()
        info = market.get(stock_id)
        if not info:
            await callback.answer("❌ Акция не найдена на рынке", show_alert=True)
            return
        owned = len(user_stocks)
        kb = make_sell_options_kb(user_id, int(stock_id), owned)
        await callback.message.edit_text(
            f"📤 {info['name']} — {price(info['price'], 2)}$\nВыберите опцию:", reply_markup=kb
        )
    except Exception:
        await error_report(
            callback.message, bot, "sell_stock_item", traceback.format_exc()
        )


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "quick_sell"))
async def cb_quick_sell(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        stock_id = str(callback_data.stock_id)
        qty = int(callback_data.qty or 1)
        items = await db.get_global_user_param(user_id, "items") or []
        matching = [
            i
            for i in items
            if i.get("type") == "stock" and str(i.get("id")) == stock_id
        ]
        if len(matching) < qty:
            await callback.answer(
                "📭 У вас нет столько акций для продажи", show_alert=True
            )
            return
        market = load_stocks()
        info = market.get(stock_id, {})
        current_price = price(info.get("price", 0), 2)
        removed = 0
        buy_total = 0
        for idx in reversed(range(len(items))):
            if removed >= qty:
                break
            it = items[idx]
            if it.get("type") == "stock" and str(it.get("id")) == stock_id:
                buy_total += it.get("price", 0)
                del items[idx]
                removed += 1
        user_bal = await db.get_global_user_param(user_id, "money") or 0
        total_get = price(current_price * qty, 2)
        await db.set_global_user_param(user_id, "money", user_bal + total_get)
        await db.set_global_user_param(user_id, "items", items)
        avg_buy = round((buy_total / qty), 2) if qty > 0 else 0
        profit = total_get - buy_total
        stock_name = info.get("name", "Акция")
        if profit >= 0:
            profit_message = f"🟢 Прибыль: {profit:.2f}$"
        else:
            profit_message = f"🔴 Убыток: {profit:.2f}$"
        answer_text = f"✅ Продана акция '{stock_name}' x{qty}\n💰 Получено: {total_get}$ (ср. цена покупки: {avg_buy:.2f}$)\n{profit_message}"
        await callback.answer(answer_text, show_alert=True)
        await callback.message.edit_text(
            f"👋 Привет, {callback.from_user.first_name}, выбери опцию:",
            reply_markup=make_menu_kb(user_id),
        )
    except Exception:
        await error_report(callback.message, bot, "quick_sell", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "ask_sell_qty"))
async def cb_ask_sell_qty(
    callback: CallbackQuery,
    bot: Bot,
    db: Database,
    callback_data: InvestMenuCallback,
    state: FSMContext,
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        stock_id = callback_data.stock_id
        items = await db.get_global_user_param(user_id, "items") or []
        user_stocks = [
            i
            for i in items
            if i.get("type") == "stock" and str(i.get("id")) == str(stock_id)
        ]
        if not user_stocks:
            await callback.answer("📭 У вас нет этой акции", show_alert=True)
            return
        await state.update_data(action="sell", user_id=user_id, stock_id=stock_id)
        await callback.message.answer(
            "Введите количество для продажи (целое число):",
            reply_markup=ForceReply(selective=True),
        )
        await state.set_state(AskQty.waiting_qty)
        await callback.answer()
    except Exception:
        await error_report(
            callback.message, bot, "ask_sell_qty", traceback.format_exc()
        )


@invest_router.message(AskQty.waiting_qty)
async def process_entered_qty(
    message: Message, state: FSMContext, db: Database, bot: Bot
):
    try:
        data = await state.get_data()
        if message.from_user.id != data.get("user_id"):
            await message.answer("📛 Это не ваш ввод.")
            await state.clear()
            return
        try:
            qty = int(message.text.strip())
        except Exception:
            await message.answer("Пожалуйста, введите корректное целое число.")
            return
        if qty <= 0:
            await message.answer("Количество должно быть > 0.")
            await state.clear()
            return
        action = data.get("action")
        stock_id = data.get("stock_id")
        stocks = load_stocks()
        stock = stocks.get(str(stock_id))
        if action == "buy":
            if not stock:
                await message.answer("❌ Акция больше не найдена на рынке.")
                await state.clear()
                return
            price = round(stock["price"], 2)
            user_bal = (
                await db.get_global_user_param(message.from_user.id, "money") or 0
            )
            MAX_LIMIT = 1000
            allowed_max = max(
                1, min(MAX_LIMIT, int(user_bal // price) if price > 0 else MAX_LIMIT)
            )
            if qty > allowed_max:
                await message.answer(
                    f"⚠️ Недостаточно денег или превышен лимит. Максимум: {allowed_max}"
                )
                await state.clear()
                return
            total_cost = round(price * qty, 2)
            await db.set_global_user_param(
                message.from_user.id, "money", user_bal - total_cost
            )
            items = await db.get_global_user_param(message.from_user.id, "items") or []
            if not isinstance(items, list):
                items = []
            for _ in range(qty):
                items.append({"type": "stock", "id": stock_id, "price": price})
            await db.set_global_user_param(message.from_user.id, "items", items)
            await message.answer(f"✅ Куплено: {stock['name']} x{qty} за {total_cost}$")
            await state.clear()
            return
        if action == "sell":
            items = await db.get_global_user_param(message.from_user.id, "items") or []
            matching = [
                i
                for i in items
                if i.get("type") == "stock" and str(i.get("id")) == str(stock_id)
            ]
            if len(matching) < qty:
                await message.answer("📭 У вас нет столько акций для продажи")
                await state.clear()
                return
            market = load_stocks()
            info = market.get(str(stock_id), {})
            current_price = info.get("price", 0)
            removed = 0
            buy_total = 0
            for idx in reversed(range(len(items))):
                if removed >= qty:
                    break
                it = items[idx]
                if it.get("type") == "stock" and str(it.get("id")) == str(stock_id):
                    buy_total += it.get("price", 0)
                    del items[idx]
                    removed += 1
            user_bal = (
                await db.get_global_user_param(message.from_user.id, "money") or 0
            )
            total_get = round(current_price * qty, 2)
            await db.set_global_user_param(
                message.from_user.id, "money", user_bal + total_get
            )
            await db.set_global_user_param(message.from_user.id, "items", items)
            avg_buy = (buy_total / qty) if qty > 0 else 0
            profit = total_get - buy_total
            stock_name = info.get("name", "Акция")
            if profit >= 0:
                profit_message = f"🟢 Прибыль: {profit:.2f}$"
            else:
                profit_message = f"🔴 Убыток: {profit:.2f}$"
            answer_text = f"✅ Продана акция '{stock_name}' x{qty}\n💰 Получено: {total_get}$ (ср. цена покупки: {avg_buy:.2f}$)\n{profit_message}"
            await message.answer(answer_text)
            await state.clear()
            return
        await state.clear()
    except Exception:
        await error_report(message, bot, "process_entered_qty", traceback.format_exc())


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "my_portfolio"))
async def cb_my_portfolio(
    callback: CallbackQuery, bot: Bot, db: Database, callback_data: InvestMenuCallback
):
    try:
        user_id = callback.from_user.id
        if user_id != callback_data.user_id:
            await callback.answer("📛 Не ваш колбэк!")
            return
        items = await db.get_global_user_param(user_id, "items") or []
        stocks = [i for i in items if i.get("type") == "stock"]
        if not stocks:
            await callback.answer("📭 Портфель пуст", show_alert=True)
            return
        market = load_stocks()
        total_value = 0
        summary = {}
        for s in stocks:
            info = market.get(str(s["id"]))
            if not info:
                continue
            name = info["name"]
            current_price = price(info["price"], 2)
            if name not in summary:
                summary[name] = {"count": 0, "current_total": 0, "buy_total": 0}
            summary[name]["count"] += 1
            summary[name]["current_total"] += current_price
            summary[name]["buy_total"] += s["price"]
        text = "💼 Ваш портфель:\n"
        for name, data in summary.items():
            avg_buy = round(data["buy_total"] / data["count"], 2)
            cur_per = round(data["current_total"] / data["count"], 2)
            text += f"- {name} ({data['count']} шт.): {cur_per}$ за шт. (ср. цена покупки: {avg_buy:.2f}$)\n"
            total_value += data["current_total"]
        text += f"\n💰 Общая стоимость: {total_value}$"
        await callback.message.edit_text(text, reply_markup=make_portfolio_kb(user_id))
    except Exception:
        await error_report(
            callback.message, bot, "my_portfolio", traceback.format_exc()
        )


@invest_router.callback_query(InvestMenuCallback.filter(F.action == "back_to_menu"))
async def cb_back(callback: CallbackQuery, bot: Bot, callback_data: InvestMenuCallback):
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
        await error_report(
            callback.message, bot, "back_to_menu", traceback.format_exc()
        )
