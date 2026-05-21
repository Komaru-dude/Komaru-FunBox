from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callback_data import PremiumBuyCallback


def make_premium_kb(user_id: int, is_premium: bool) -> InlineKeyboardMarkup:
    have_premium_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Продлить премиум (+30 дней)",
                    callback_data=PremiumBuyCallback(
                        action="extend", user_id=user_id, time=30
                    ).pack(),
                )
            ]
        ]
    )
    no_premium_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Купить премиум на 30 дней",
                    callback_data=PremiumBuyCallback(
                        action="buy", user_id=user_id, time=30
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Что такое премиум?",
                    callback_data=PremiumBuyCallback(
                        action="info", user_id=user_id
                    ).pack(),
                )
            ],
        ]
    )
    return have_premium_kb if is_premium else no_premium_kb
