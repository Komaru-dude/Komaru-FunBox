from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import CATEGORIES, DEFAULT_SETTINGS


def main_settings_keyboard():
    builder = InlineKeyboardBuilder()
    for category in CATEGORIES:
        builder.button(text=category, callback_data=f"category:{category}")
    builder.button(text="🔒 Закрыть", callback_data="close_settings")
    builder.adjust(2)
    return builder.as_markup()


def category_settings_keyboard(category: str, settings_state: dict):
    builder = InlineKeyboardBuilder()

    # Фильтруем настройки по категории
    for setting in DEFAULT_SETTINGS:
        if setting[1] == category:
            name = setting[0]
            value = settings_state.get(name)

            if value is None and len(setting) > 3:
                value = setting[3]

            # Форматирование значения
            if value is None:
                display = "❓ Не установлено"
            elif isinstance(value, bool):
                display = "✅ Вкл" if value else "❌ Выкл"
            elif isinstance(value, int):
                display = f"🔢 {value}"
            elif isinstance(value, str):
                display = f"✏️ {value[:15] + '...' if len(value) > 15 else value}"
            else:
                display = f"⚙️ {str(value)}"

            builder.button(
                text=f"{setting[0]}: {display}", callback_data=f"setting:{name}"
            )

    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def setting_options_keyboard(setting_name: str, current_value):
    builder = InlineKeyboardBuilder()
    setting = next((s for s in DEFAULT_SETTINGS if s[0] == setting_name), None)

    if not setting:
        builder.button(text="❌ Ошибка: настройка не найдена", callback_data="noop")
        return builder.as_markup()

    # Булевые настройки
    if setting[2] is bool:
        builder.button(
            text="✅ Включено" if current_value else "❌ Выключено",
            callback_data=f"toggle_bool:{setting_name}",
        )
        builder.button(
            text="🔄 Переключить",
            callback_data=f"toggle_bool:{setting_name}",
        )

    # Числовые настройки
    elif setting[2] is int:
        builder.button(text="➖", callback_data=f"change_int:{setting_name}:-1")
        builder.button(text=f"{current_value}", callback_data="noop")
        builder.button(text="➕", callback_data=f"change_int:{setting_name}:+1")
        builder.button(text="✏️ Ввести число", callback_data=f"input_int:{setting_name}")

    # Список вариантов
    elif setting[2] is list and len(setting) > 3:
        for option in setting[3]:
            is_selected = "🔘" if option == current_value else "⚪️"
            builder.button(
                text=f"{is_selected} {option}",
                callback_data=f"select_option:{setting_name}:{option}",
            )

    # Строковые настройки
    elif setting[2] is str:
        builder.button(
            text="✏️ Изменить текст", callback_data=f"input_str:{setting_name}"
        )

    else:
        builder.button(
            text="✏️ Изменить значение", callback_data=f"input_str:{setting_name}"
        )

    builder.button(text="⬅️ Назад", callback_data=f"back_to_category:{setting[1]}")
    builder.adjust(1)
    return builder.as_markup()
