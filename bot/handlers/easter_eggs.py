from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from pathlib import Path

easter_router = Router()

@easter_router.message(Command("cafe"))
async def cmd_tea(message: Message):
    file_path = Path(__file__).parent.parent / 'media' / '418.jpg'
    t418 = FSInputFile(file_path)
    await message.reply_photo(t418, caption="418 I'm a <i>teapot</i> ☕", parse_mode=ParseMode.HTML)