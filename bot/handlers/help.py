import aiohttp
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from urllib.parse import quote

help_router = Router()

BASE_WIKI_URL = "https://komaru-dude.github.io/Komaru-FunBox/docs/commands"


async def check_wiki_page(url):
    async with aiohttp.ClientSession() as session:
        async with session.head(url) as response:
            return response.status == 200 or response.status == 301


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
        if await check_wiki_page(url):
            await message.reply(
                f"Подробная информация о команде '{argument}':\n{url}",
                disable_web_page_preview=True,
            )
        else:
            await message.reply(
                f"Команда '{argument}' не найдена в вики.\nПолный список команд: {BASE_WIKI_URL}/",
                disable_web_page_preview=True,
            )
