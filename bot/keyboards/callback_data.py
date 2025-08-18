from aiogram.filters.callback_data import CallbackData


class InvestMenuCallback(CallbackData, prefix="imenu"):
    action: str
    user_id: int
    stock_id: int = 0
    item_idx: int = None
