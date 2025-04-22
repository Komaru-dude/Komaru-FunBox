import os, subprocess
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from bot import db
from bot.utils.aio_tools import fetch_json

mods_router = Router()
API_URL = "http://127.0.0.1:8001"

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

@mods_router.message(Command("history"))
async def cmd_history(message: Message):
    user_id = message.from_user.id
    history = db.get_history(user_id)
    
    if not history:
        await message.reply("У вас пока нет наказаний.")
        return

    history_text = ""
    for i, entry in enumerate(history, start=1):
        punishment_type = entry["type"]
        reason = entry.get("reason", "Без причины")
        history_text += f"{i}. {punishment_type.capitalize()} - Причина: {reason}.\n"
    
    warns_count = len(history)
    response = (
        f"Всего наказаний: {warns_count}\n"
        f"История наказаний:\n{history_text}"
    )
    await message.reply(response)
    
