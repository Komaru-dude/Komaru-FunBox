from typing import Optional

from aiogram.filters.callback_data import CallbackData


class InvestMenuCallback(CallbackData, prefix="imenu"):
    action: str
    user_id: int
    stock_id: Optional[int] = None
    qty: Optional[int] = None


class WeatherCallback(CallbackData, prefix="weather"):
    day: int
    user_id: int


class PromptsMenuCallback(CallbackData, prefix="pmenu"):
    action: str
    user_id: int
    prompt_id: str = "none"


class EditPromptCallback(CallbackData, prefix="edp"):
    action: str
    prompt_id: str
    user_id: int


class EditFieldCallback(CallbackData, prefix="edf"):
    field: str  # title, content, public, save
    prompt_id: str
    user_id: int


class PremiumBuyCallback(CallbackData, prefix="premium"):
    action: str
    user_id: int
    time: Optional[int] = None


class SetModelCallback(CallbackData, prefix="setmodel"):
    model: str
    user_id: int
    type: str  # 'text' или 'image'


class SetDefaultModelCallback(CallbackData, prefix="setdefaultmodel"):
    user_id: int
    type: str  # 'text' или 'image'
