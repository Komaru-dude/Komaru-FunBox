import aiohttp
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db

tag_router = Router()

async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

@tag_router.message(Command("tag"))
async def cmd_tag(message: Message):
    chat_id = message.chat.id
    split_text = message.text.split()

    if not db.is_feature_enabled(chat_id, "tag") and not db.has_permission(message.from_user.id, chat_id, 1):
        await message.reply("❌ Функция не включена в чате, а вы не имеете прав модератора.")
        return
    
    if len(message.text) < 2:
        await message.reply("❌ А кого упоминать?")
        return
    
    if split_text[1].isdigit:
        tag_id = message.text.split(maxsplit=1)[1]
    else:
        await message.reply("❌ Вы не указали кого упоминать(или указали некорректно).")
    
    await message.answer(f'Вы были упомянуты!<a href="tg://user?id={tag_id}">\u2060</a>', parse_mode=ParseMode.HTML)