import aiohttp, os, subprocess, uuid
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from bot import db

mods_router = Router()
API_URL = "http://127.0.0.1:8001"

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка API: статус {response.status}")
            return await response.json()

@mods_router.message(Command("restart"))
async def cmd_restart(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    await message.answer("Перезапускаюсь... 🔄")

    try:
        subprocess.Popen(["sudo", "systemctl", "restart", "komaru-funbox.service"])
    except Exception as e:
        await message.reply("Не удалось перезагрузиться!")
        await bot.send_message(chat_id=os.getenv("OWNER_ID"), 
                                text=f"Во время обработки команды /restart произошла ошибка: {e}")

@mods_router.message(Command("enable"))
async def cmd_enable_func(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⛔️ Укажите имя функции.")
        return
    func = parts[1]
    
    if not db.is_feature_exists(chat_id, func):
        await message.reply("❌ Функции не существует.")
        return
    
    if not db.has_permission(user_id, chat_id, 2):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    
    if db.is_feature_enabled(chat_id, func):
        await message.reply("❌ Функция уже включена.")
        return

    try:
        db.enable_feature(chat_id, func)
        await message.reply("✅ Функция включена.")
    except Exception as e:
        await message.reply("❌ Не удалось включить функцию.")
        await bot.send_message(os.getenv("OWNER_ID"), text=f"Во время выполнения /enable произошла ошибка: {e}")

@mods_router.message(Command("disable"))
async def cmd_disable_func(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("⛔️ Укажите имя функции.")
        return
    func = parts[1]
    
    if not db.is_feature_exists(chat_id, func):
        await message.reply("❌ Функции не существует.")
        return
    
    if not db.has_permission(user_id, chat_id, 2):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    
    if not db.is_feature_enabled(chat_id, func):
        await message.reply("❌ Функция уже выключена.")
        return

    try:
        db.disable_feature(chat_id, func)
        await message.reply("✅ Функция выключена.")
    except Exception as e:
        await message.reply("❌ Не удалось выключить функцию.")
        await bot.send_message(os.getenv("OWNER_ID"), text=f"Во время выполнения /disable произошла ошибка: {e}")