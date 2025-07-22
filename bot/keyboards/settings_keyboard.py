from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_features_keyboard(features: list[tuple[str, bool]]):
    builder = InlineKeyboardBuilder()

    for feature, enabled in features:
        status = "✅" if enabled else "❌"
        builder.button(text=f"{status} {feature}", callback_data=f"toggle:{feature}")

    builder.button(text="🔙 Закрыть", callback_data="close")
    builder.adjust(2, repeat=True)
    return builder.as_markup()
