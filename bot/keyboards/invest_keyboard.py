import json
from typing import Dict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import STOCKS_PATH, logger

from .callback_data import InvestMenuCallback


def load_stocks() -> Dict:
    try:
        with open(STOCKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("stocks not found")
        return {}


def make_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
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


def make_stocks_kb(user_id: int) -> InlineKeyboardMarkup:
    stocks = load_stocks()
    rows = []
    for stock_id, stock in stocks.items():
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{stock['name']} — {round(stock['price']}, 2)$",
                    callback_data=InvestMenuCallback(
                        action="buy_stock_item", user_id=user_id, stock_id=int(stock_id)
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=InvestMenuCallback(
                    action="back_to_menu", user_id=user_id
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_buy_options_kb(
    user_id: int, stock_id: int, price: float, user_bal: float, max_limit: int = 1000
) -> InlineKeyboardMarkup:
    price = round(price, 2)
    max_by_money = int(user_bal // price) if price > 0 else max_limit
    allowed_max = max(1, min(max_limit, max_by_money))
    presets = [1, 5, 10]
    row = []
    for p in presets:
        row.append(
            InlineKeyboardButton(
                text=f"x{p}",
                callback_data=InvestMenuCallback(
                    action="quick_buy", user_id=user_id, stock_id=stock_id, qty=p
                ).pack(),
            )
        )
    row.append(
        InlineKeyboardButton(
            text="Max",
            callback_data=InvestMenuCallback(
                action="quick_buy", user_id=user_id, stock_id=stock_id, qty=allowed_max
            ).pack(),
        )
    )
    rows = [
        row,
        [
            InlineKeyboardButton(
                text="Другое",
                callback_data=InvestMenuCallback(
                    action="ask_buy_qty", user_id=user_id, stock_id=stock_id
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=InvestMenuCallback(
                    action="buy_stock", user_id=user_id
                ).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_sell_stocks_kb(
    user_id: int, user_stocks: list, market: Dict
) -> InlineKeyboardMarkup:
    grouped = {}
    for s in user_stocks:
        sid = str(s["id"])
        if sid not in grouped:
            grouped[sid] = {"count": 0, "total_buy_price": 0}
        grouped[sid]["count"] += 1
        grouped[sid]["total_buy_price"] += s.get("price", 0)
    rows = []
    for stock_id, data in grouped.items():
        info = market.get(stock_id)
        if not info:
            continue
        cp = round(info["price"], 2)
        text = f"{info['name']} ({data['count']} шт.)\n📈 {cp}$ / шт."
        rows.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=InvestMenuCallback(
                        action="sell_stock_item",
                        user_id=user_id,
                        stock_id=int(stock_id),
                    ).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=InvestMenuCallback(
                    action="back_to_menu", user_id=user_id
                ).pack(),
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_sell_options_kb(
    user_id: int, stock_id: int, owned_count: int
) -> InlineKeyboardMarkup:
    presets = [1, 5, 10]
    row = []
    for p in presets:
        if p <= owned_count:
            row.append(
                InlineKeyboardButton(
                    text=f"x{p}",
                    callback_data=InvestMenuCallback(
                        action="quick_sell", user_id=user_id, stock_id=stock_id, qty=p
                    ).pack(),
                )
            )
    row.append(
        InlineKeyboardButton(
            text="Max",
            callback_data=InvestMenuCallback(
                action="quick_sell", user_id=user_id, stock_id=stock_id, qty=owned_count
            ).pack(),
        )
    )
    rows = [
        row,
        [
            InlineKeyboardButton(
                text="Другое",
                callback_data=InvestMenuCallback(
                    action="ask_sell_qty", user_id=user_id, stock_id=stock_id
                ).pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=InvestMenuCallback(
                    action="sell_stock", user_id=user_id
                ).pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_portfolio_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
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
