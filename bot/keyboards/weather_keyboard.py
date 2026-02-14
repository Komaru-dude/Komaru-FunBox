from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callback_data import WeatherCallback


def create_days_keyboard(current_day_delta: int, user_id: int) -> InlineKeyboardMarkup:
    inline_keyboard = []
    nav_row = []

    if current_day_delta > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=WeatherCallback(
                    day=current_day_delta - 1, user_id=user_id
                ).pack(),
            )
        )

    today_date = datetime.now()
    target_date = today_date + timedelta(days=current_day_delta)
    day_name = target_date.strftime("%a, %b %d")
    nav_row.append(
        InlineKeyboardButton(
            text=f"🗓 {day_name}",
            callback_data="ignore",
        )
    )

    if current_day_delta < 2:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=WeatherCallback(
                    day=current_day_delta + 1, user_id=user_id
                ).pack(),
            )
        )

    inline_keyboard.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
