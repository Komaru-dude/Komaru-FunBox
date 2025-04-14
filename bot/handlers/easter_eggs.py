from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from pathlib import Path

easter_router = Router()

@easter_router.message(Command("coffee"))
async def cmd_tea(message: Message):
    file_path = Path(__file__).parent.parent / 'media' / '418.jpg'
    t418 = FSInputFile(file_path)
    if message.reply_to_message:
        await message.reply_to_message.reply_photo(t418, caption="418 I'm a <a href='https://ru.wikipedia.org/wiki/HTCPCP'>teapot</a> ☕", parse_mode=ParseMode.HTML)
    else:
        await message.reply_photo(t418, caption="418 I'm a <i>teapot</i> ☕", parse_mode=ParseMode.HTML)

@easter_router.message(Command("tag"))
async def cmd_tag(message: Message):
    await message.answer('<a href="tg://user?id=123456789">\u2060</a>', parse_mode=ParseMode.HTML)