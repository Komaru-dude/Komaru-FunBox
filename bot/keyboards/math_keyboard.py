from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def make_math_kb(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 Лёгкая", callback_data=f"math_easy_{user_id}"
                ),
                InlineKeyboardButton(
                    text="🟡 Средняя", callback_data=f"math_medium_{user_id}"
                ),
                InlineKeyboardButton(
                    text="🔴 Сложная", callback_data=f"math_hard_{user_id}"
                ),
            ]
        ]
    )
