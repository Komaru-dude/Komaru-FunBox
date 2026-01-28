from typing import Optional

from aiogram.filters.callback_data import CallbackData


class InvestMenuCallback(CallbackData, prefix="imenu"):
    action: str
    user_id: int
    stock_id: Optional[int] = None
    qty: Optional[int] = None
