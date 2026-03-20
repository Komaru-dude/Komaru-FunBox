from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.callback_data import PromptsMenuCallback


def make_pmenu_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="➕ Добавить промпт",
        callback_data=PromptsMenuCallback(action="add_pr", user_id=user_id),
    )
    builder.button(
        text="📥 Добавить промпт по ID",
        callback_data=PromptsMenuCallback(action="import_pr", user_id=user_id),
    )
    builder.button(
        text="📋 Мои промпты",
        callback_data=PromptsMenuCallback(action="list_prompts", user_id=user_id),
    )
    return builder.as_markup()


def make_pmenu_back_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(
        text="◀️ Назад",
        callback_data=PromptsMenuCallback(action="show_menu", user_id=user_id),
    )
    return builder.as_markup()


def make_prompt_manage_keyboard(user_id: int, prompt_id: str):
    builder = InlineKeyboardBuilder()

    # Осторожно с лимитами. Они уже из-за uuid у "края"
    builder.button(
        text="✏️ Название",
        callback_data=PromptsMenuCallback(
            action="edt", user_id=user_id, prompt_id=prompt_id
        ),
    )
    builder.button(
        text="📄 Текст",
        callback_data=PromptsMenuCallback(
            action="edc", user_id=user_id, prompt_id=prompt_id
        ),
    )
    builder.button(
        text="🌐 Доступ",
        callback_data=PromptsMenuCallback(
            action="tgpub", user_id=user_id, prompt_id=prompt_id
        ),
    )
    builder.button(
        text="🗑 Удалить",
        callback_data=PromptsMenuCallback(
            action="delpr", user_id=user_id, prompt_id=prompt_id
        ),
    )
    builder.button(
        text="◀️ Назад к списку",
        callback_data=PromptsMenuCallback(action="list_prompts", user_id=user_id),
    )
    builder.adjust(2, 1, 1)

    return builder.as_markup()
