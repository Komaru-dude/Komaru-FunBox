from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import CATEGORIES, DEFAULT_SETTINGS


def main_settings_keyboard(owner_id: int):
    builder = InlineKeyboardBuilder()
    for category in CATEGORIES:
        builder.button(text=category, callback_data=f"category:{category}:{owner_id}")
    builder.button(text="🔒 Закрыть", callback_data=f"close_settings:{owner_id}")
    builder.adjust(2)
    return builder.as_markup()


def category_settings_keyboard(category: str, settings_state: dict, owner_id: int):
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
                display = f"✏️ {value[:15]+'...' if len(value)>15 else value}"
            else:
                display = f"⚙️ {value}"

            builder.button(
                text=f"{name}: {display}", callback_data=f"setting:{name}:{owner_id}"
            )

    builder.button(text="⬅️ Назад", callback_data=f"back_to_main:{owner_id}")
    builder.adjust(1)
    return builder.as_markup()


def setting_options_keyboard(setting_name: str, current_value, owner_id: int):
    builder = InlineKeyboardBuilder()
    setting = next((s for s in DEFAULT_SETTINGS if s[0] == setting_name), None)
    if not setting:
        builder.button(text="❌ Ошибка", callback_data="noop")
        builder.adjust(1)
        return builder.as_markup()

    # Булевые
    if setting[2] is bool:
        builder.button(
            text="🔄 Переключить",
            callback_data=f"toggle_bool:{setting_name}:{owner_id}",
        )
    # Int
    elif setting[2] is int:
        builder.button(
            text="➖", callback_data=f"change_int:{setting_name}:-1:{owner_id}"
        )
        builder.button(text=f"{current_value}", callback_data="noop")
        builder.button(
            text="➕", callback_data=f"change_int:{setting_name}:+1:{owner_id}"
        )
        builder.button(
            text="✏️ Ввести число", callback_data=f"input_int:{setting_name}:{owner_id}"
        )
    # Float
    elif setting[2] is float:
        builder.button(
            text="✏️ Ввести число с плавающей точкой",
            callback_data=f"input_float:{setting_name}:{owner_id}",
        )
    # Список
    elif setting[2] is list and len(setting) > 3:
        for option in setting[3]:
            mark = "🔘" if option == current_value else "⚪️"
            builder.button(
                text=f"{mark} {option}",
                callback_data=f"select_option:{setting_name}:{option}:{owner_id}",
            )
    # Str
    else:
        builder.button(
            text="✏️ Изменить текст",
            callback_data=f"input_str:{setting_name}:{owner_id}",
        )

    builder.button(
        text="⬅️ Назад", callback_data=f"back_to_category:{setting[1]}:{owner_id}"
    )
    builder.adjust(1)
    return builder.as_markup()


def restore_settings_keyboard(owner_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="❎ Нет", callback_data=f"restore_default_settings:no:{owner_id}"
    )
    builder.button(
        text="✅ Да", callback_data=f"restore_default_settings:yes:{owner_id}"
    )
    builder.adjust(2)
    return builder.as_markup()
