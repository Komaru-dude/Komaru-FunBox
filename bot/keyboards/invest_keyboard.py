import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import STOCKS_PATH, logger

from .callback_data import InvestMenuCallback


def load_stocks() -> dict:
    try:
        with open(STOCKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("📛 Не удалось загрузить стоки.")
        return {}


def make_menu_kb(user_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💼 Мой портфель",
                    callback_data=InvestMenuCallback(
                        action="my_portfolio", user_id=user_id
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛒 Купить акции",
                    callback_data=InvestMenuCallback(
                        action="buy_stock", user_id=user_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="💸 Продать акции",
                    callback_data=InvestMenuCallback(
                        action="sell_stock", user_id=user_id
                    ).pack(),
                ),
            ],
        ]
    )
    return keyboard


def make_stocks_kb(user_id: int):
    stocks = load_stocks()
    keyboard_rows = []
    for stock_id, stock in stocks.items():
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"{stock['name']} — {stock['price']}$",
                    callback_data=InvestMenuCallback(
                        action="buy_stock_item", user_id=user_id, stock_id=int(stock_id)
                    ).pack(),
                )
            ]
        )
    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=InvestMenuCallback(
                    action="back_to_menu", user_id=user_id
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def make_sell_stocks_kb(user_id, user_stocks, market):
    grouped_stocks = {}
    for i, stock in enumerate(user_stocks):
        stock_id = str(stock["id"])
        if stock_id not in grouped_stocks:
            grouped_stocks[stock_id] = {
                "count": 0,
                "first_index": i,
            }
        grouped_stocks[stock_id]["count"] += 1

    keyboard_rows = []
    for stock_id, data in grouped_stocks.items():
        stock_info = market.get(stock_id)
        if stock_info:
            text = f"Продать {stock_info['name']} ({data['count']} шт.)"
            callback_data = InvestMenuCallback(
                user_id=user_id,
                action="sell_stock_item",
                stock_id=int(stock_id),
                item_idx=data["first_index"],
            ).pack()
            keyboard_rows.append(
                [InlineKeyboardButton(text=text, callback_data=callback_data)]
            )

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=InvestMenuCallback(
                    user_id=user_id, action="back_to_menu"
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def make_portfolio_kb(user_id: int):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=InvestMenuCallback(
                        action="back_to_menu", user_id=user_id
                    ).pack(),
                )
            ]
        ]
    )
    return keyboard
