import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import db
from pathlib import Path

rp_router = Router()
BASE_COMMANDS_PATH = Path("bot/basic_rp.json")
CUSTOM_DIR = Path("data/rp_commands")
CUSTOM_DIR.mkdir(parents=True, exist_ok=True)

def load_commands(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_custom_commands(chat_id: int, commands: dict):
    custom_path = CUSTOM_DIR / f"{chat_id}.json"
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(commands, f, ensure_ascii=False, indent=2)

def get_chat_commands(chat_id: int):
    custom_path = CUSTOM_DIR / f"{chat_id}.json"
    
    if custom_path.exists():
        custom_commands = {cmd["command"]: cmd for cmd in load_commands(custom_path)}
        return custom_commands
    
    return {}

@rp_router.message(Command("rp_setup"))
async def rp_setup_cmd(message: Message):
    user_id = message.from_user.id

    if not db.has_permission(user_id, 2):
        await message.reply("У вас недостаточно прав для выполнению этой команды")
        return

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Да", callback_data="Yes"))
    builder.add(InlineKeyboardButton(text="Нет", callback_data="No"))

    await message.reply("Вы уверены? Это приведёт к сбросу уже существующих команд (/rp_list)", reply_markup=builder.as_markup())

@rp_router.callback_query(F.data == "Yes")
async def rp_setup_yes(callback: CallbackQuery):
    await callback.message.reply("Успешно сброшено!")
    chat_id = callback.message.chat.id
    base_commands = load_commands(BASE_COMMANDS_PATH)
    save_custom_commands(chat_id, base_commands)

@rp_router.callback_query(F.data == "No")
async def rp_setup_no(callback: CallbackQuery):
    await callback.message.reply("Отмена")

@rp_router.message(Command("rp_list"))
async def rp_list_cmd(message: Message):
    chat_id = message.chat.id
    commands = get_chat_commands(chat_id)
    
    if not commands:
        await message.reply("В этом чате нет доступных RP-команд.")
        return
    
    command_list = "\n".join(f"{cmd['command']} - {cmd['description']}" for cmd in commands.values())
    await message.reply(f"Доступные RP-команды:\n{command_list}")