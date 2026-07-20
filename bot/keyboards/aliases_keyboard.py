from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callback_data import AliasMenuCallback


def make_aliases_menu_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Добавить алиас",
        callback_data=AliasMenuCallback(action="add", user_id=user_id),
    )
    builder.button(
        text="📋 Мои алиасы",
        callback_data=AliasMenuCallback(action="list", user_id=user_id),
    )
    builder.button(
        text="📦 Загрузить пресет",
        callback_data=AliasMenuCallback(action="preset", user_id=user_id),
    )
    builder.adjust(1)
    return builder.as_markup()


def make_aliases_back_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="◀️ В главное меню",
        callback_data=AliasMenuCallback(action="menu", user_id=user_id),
    )
    return builder.as_markup()


def make_aliases_list_keyboard(user_id: int, aliases: dict[str, str]):
    builder = InlineKeyboardBuilder()
    for alias, target in sorted(aliases.items()):
        builder.button(
            text=f"{alias} → /{target}",
            callback_data=AliasMenuCallback(
                action="delete", user_id=user_id, alias=alias
            ),
        )
    builder.button(
        text="◀️ В главное меню",
        callback_data=AliasMenuCallback(action="menu", user_id=user_id),
    )
    builder.adjust(1)
    return builder.as_markup()
