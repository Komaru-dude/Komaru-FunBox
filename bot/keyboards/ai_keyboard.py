from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callback_data import SetModelCallback
from bot.utils.global_storage import filtered_models

MODELS_PER_PAGE = 8


def make_available_models_kb(
    user_id: int, models_ids: list, page: int = 0
) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора моделей с пагинацией."""
    inline_keyboard = []

    start_idx = page * MODELS_PER_PAGE
    end_idx = start_idx + MODELS_PER_PAGE
    page_models = models_ids[start_idx:end_idx]

    for model_id in page_models:
        model = filtered_models.get(model_id)
        if model:
            premium_icon = " 💎" if model.get("is_premium", False) else ""
            thinking_icon = " 🧠" if model.get("can-think", False) else ""
            tools_icon = " 🔧" if model.get("can-tools", False) else ""
            model_name = f"{model_id}{premium_icon}{thinking_icon}{tools_icon}"

            inline_keyboard.append(
                [
                    InlineKeyboardButton(
                        text=model_name,
                        callback_data=SetModelCallback(
                            model=model_id,
                            user_id=user_id,
                            type=model.get("modality", "text"),
                        ).pack(),
                    )
                ]
            )

    navigation = []
    total_pages = (len(models_ids) + MODELS_PER_PAGE - 1) // MODELS_PER_PAGE

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"models_page:{user_id}:{page-1}"
            )
        )

    navigation.append(
        InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop")
    )

    if page < total_pages - 1:
        navigation.append(
            InlineKeyboardButton(
                text="Вперед ➡️", callback_data=f"models_page:{user_id}:{page+1}"
            )
        )

    if navigation:
        inline_keyboard.append(navigation)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
