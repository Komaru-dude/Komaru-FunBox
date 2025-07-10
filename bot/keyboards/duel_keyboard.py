from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder


class DuelCallback(CallbackData, prefix="duel"):
    duel_id: str
    action: str  # accept / decline


def make_duel_keyboard(duel_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Принять",
        callback_data=DuelCallback(duel_id=duel_id, action="accept").pack(),
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=DuelCallback(duel_id=duel_id, action="decline").pack(),
    )
    return builder.as_markup()


def make_duel_actions_keyboard(duel_id: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗡 Удар", callback_data=f"duel_action:{duel_id}:attack")
    builder.button(text="🛡 Увернуться", callback_data=f"duel_action:{duel_id}:dodge")
    builder.button(text="💊 Лечение", callback_data=f"duel_action:{duel_id}:heal")
    return builder.as_markup()
