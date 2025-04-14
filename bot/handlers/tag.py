import aiohttp, json
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

@tag_router.message(Command("tagall"))
async def cmd_tagall(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ Эта команда работает только в группах и супергруппах.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    if not db.is_feature_enabled(chat_id, "tag") and not db.has_permission(user_id, chat_id, 1):
        await message.reply("❌ Функция не включена в чате, а вы не имеете прав модератора.")
        return

    try:
        url = f"http://127.0.0.1:8001/chat_members/{chat_id}"
        response_text = await fetch(url)
        response_data = json.loads(response_text)
        members = response_data.get("members", [])
    except aiohttp.ClientError as e:
        await message.reply("❌ Ошибка соединения с сервером.")
        return
    except json.JSONDecodeError:
        await message.reply("❌ Ошибка обработки данных участников.")
        return
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        return

    bot_id = (await message.bot.get_me()).id
    tags = [
        f'<a href="tg://user?id={member["user_id"]}">\u2060</a>'
        for member in members
        if member.get("user_id") and member["user_id"] != bot_id
    ]

    if not tags:
        await message.reply("❌ Нет участников для упоминания.")
        return

    chunk_size = 5
    chunks = [tags[i:i + chunk_size] for i in range(0, len(tags), chunk_size)]

    for idx, chunk in chunks:
        tags_str = ' '.join(chunk)
        if idx == 0:
            await message.answer(f"❗️ Упоминаю всех! {tags_str}", parse_mode=ParseMode.HTML)
        else:
            await message.answer(f"⬆️⬆️⬆️ {tags_str}", parse_mode=ParseMode.HTML)