from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from bot import database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.utils.aio_tools import error_report

eco_router = Router()
db = database.Database()


@eco_router.message(Command("work"), FuncEnabled(func_name="eco"), CooldownFilter(command="work", cooldown=14400))
async def cmd_work(message: Message, bot: Bot):
    await message.reply("1")
