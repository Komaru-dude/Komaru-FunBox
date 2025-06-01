from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from urllib.parse import quote

help_router = Router()

BASE_WIKI_URL = "https://komaru-dude.github.io/Komaru-FunBox/docs/commands"


@help_router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) == 1:
        await message.reply(
            f"Полный список команд и их описания доступны в вики:\n{BASE_WIKI_URL}/",
            disable_web_page_preview=True,
        )
    else:
        argument = parts[1].lower()
        encoded_arg = quote(argument)
        url = f"{BASE_WIKI_URL}/{encoded_arg}"
        await message.reply(
            f"Подробная информация о команде '{argument}':\n{url}",
            disable_web_page_preview=True,
        )
