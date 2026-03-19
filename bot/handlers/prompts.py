import traceback

from aiogram import Router
from aiogram.filters import Command

from bot.database.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.utils.aio_tools import error_report

prompts_router = Router()


@prompts_router.message(Command("prompts"), CooldownFilter("prompts"), 15)
async def cmd_prompts():
    try:
        assert message.from_user is not None
        user_id = message.from_user.id
    except Exception:
        await error_report(message, bot, "list_prompts", traceback.format_exc())
