from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callback_data import CaseMenuCallback


def make_cases_kb(user_id: int, cases: list) -> InlineKeyboardMarkup:
    inline_keyboard = []

    for case in cases:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{case['name']} (🪙 {case['price']} монет)",
                    callback_data=CaseMenuCallback(
                        user_id=user_id, case_id=case["id"]
                    ).pack(),
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
