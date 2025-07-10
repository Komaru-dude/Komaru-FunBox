from typing import Optional

from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.global_storage import eco_config, shop_config


class ShopCallback(CallbackData, prefix="shop"):
    action: str
    item_id: Optional[str] = None


def make_shop_keyboard(items_per_row=3):
    builder = InlineKeyboardBuilder()
    for item in shop_config:
        btn_text = f"{item['name']} — {item['price']} {eco_config["currency_sign"]}"
        callback_data = ShopCallback(action="buy", item_id=item["id"]).pack()
        builder.button(text=btn_text, callback_data=callback_data)
    builder.adjust(items_per_row)
    return builder.as_markup()
