from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from bot import database
from bot.filters import func_filter, cooldown_filter
from bot.utils.aio_tools import error_report

eco_router = Router()
db = database.Database()


@eco_router.message(Command("work"), func_filter(func_name="eco"), cooldown_filter(command="work", cooldown=14400))
async def cmd_work(message: Message, bot: Bot):
    await message.reply("1")
