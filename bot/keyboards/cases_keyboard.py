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
                        action="menu", user_id=user_id, case_id=case["id"]
                    ).pack(),
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def make_case_detail_kb(user_id: int, case: dict) -> InlineKeyboardMarkup:
    row = []
    for count in (1, 3, 5, 7):
        row.append(
            InlineKeyboardButton(
                text=f"x{count} (🪙 {case['price'] * count})",
                callback_data=CaseMenuCallback(
                    action="open", user_id=user_id, case_id=case["id"], count=count
                ).pack(),
            )
        )
    back = InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=CaseMenuCallback(
            action="back", user_id=user_id, case_id=case["id"]
        ).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[row, [back]])
