from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


class DuelCallback(CallbackData, prefix="duel"):
    action: str  # accept / decline


def make_duel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять", callback_data=DuelCallback(action="accept").pack()
    )
    builder.button(
        text="❌ Отклонить", callback_data=DuelCallback(action="decline").pack()
    )
    return builder.as_markup()


def make_duel_actions_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🗡 Удар", callback_data="duel_action:attack")
    builder.button(text="🛡 Увернуться", callback_data="duel_action:dodge")
    builder.button(text="💊 Лечение", callback_data="duel_action:heal")
    return builder.as_markup()
