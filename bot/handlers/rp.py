import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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
async def cmd_rp_setup(message: Message):
    user_id = message.from_user.id

    if message.chat.type == "private" or message.chat.type == "channel":
        await message.reply("Эта команда доступна только в группах/супергруппах")
        return

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
async def cmd_rp_list(message: Message):
    chat_id = message.chat.id
    commands = get_chat_commands(chat_id)

    if message.chat.type == "private" or message.chat.type == "channel":
        await message.reply("Эта команда доступна только в группах/супергруппах")
        return
    
    if not commands:
        await message.reply("В этом чате нет доступных RP-команд.")
        return
    
    command_list = "\n".join(f"{cmd['command']} - {cmd['description']}" for cmd in commands.values())
    await message.reply(f"Доступные RP-команды:\n{command_list}")

class AddRpCommandStates(StatesGroup):
    waiting_for_command_name = State()
    waiting_for_description = State()
    waiting_for_messages = State()

@rp_router.message(Command("rp_add"))
async def cmd_rp_add(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if message.chat.type == "private" or message.chat.type == "channel":
        await message.reply("Эта команда доступна только в группах/супергруппах")
        return

    if not db.has_permission(user_id, 2):
        await message.reply("У вас недостаточно прав для выполнению этой команды")
        return

    await message.answer(
        "🛠 Давайте создадим новую RP-команду!\n\n"
        "Шаг 1/3: Введите название команды (без /)\n"
        "Например: <code>обнять</code>\n\n"
        "❌ Для отмены введите /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AddRpCommandStates.waiting_for_command_name)

@rp_router.message(AddRpCommandStates.waiting_for_command_name)
async def process_command_name(message: Message, state: FSMContext):
    command_name = message.text.strip().lower()
    chat_id = message.chat.id
    
    if len(command_name) > 20:
        await message.reply("❌ Слишком длинное название (макс. 20 символов)")
        return
        
    cur_commands = get_chat_commands(chat_id)
    
    if command_name in cur_commands:
        await message.reply("⚠️ Такая команда уже существует. Придумайте другое название:")
        return
    
    await state.update_data(command_name=command_name)
    await message.answer(
        "✅ Отлично! Теперь:\n\n"
        "Шаг 2/3: Введите описание команды\n"
        "Например: <code>Обнять другого пользователя</code>\n\n"
        "❌ Для отмены введите /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AddRpCommandStates.waiting_for_description)

@rp_router.message(AddRpCommandStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    description = message.text.strip()
    
    if len(description) > 20:
        await message.reply("❌ Слишком длинное описание (макс. 20 символов)")
        return
        
    if not description:
        await message.reply("❌ Описание не может быть пустым. Попробуйте снова:")
        return
    
    await state.update_data(description=description)
    await message.answer(
        "📝 Теперь введите варианты сообщений для команды, разделяя их символом |\n"
        "Например: <code>{user1} обнял {user2}|{user1} нежно прижал к груди {user2}</code>\n\n"
        "❌ Для отмены введите /cancel", parse_mode=ParseMode.HTML)
    await state.set_state(AddRpCommandStates.waiting_for_messages)

@rp_router.message(AddRpCommandStates.waiting_for_messages)
async def process_messages(message: Message, state: FSMContext):
    chat_id = message.chat.id
    messages_raw = message.text.strip()
    messages_list = [msg.strip() for msg in messages_raw.split("|") if msg.strip()]
    
    if not messages_list:
        await message.reply("❌ Вы не указали ни одного сообщения. Попробуйте снова:")
        return
    
    data = await state.get_data()
    command_name = data['command_name']
    description = data['description']
    cur_commands = get_chat_commands(chat_id)
    
    # Проверка максимального количества сообщений
    if len(messages_list) > 4:
        await message.reply("⚠️ Можно добавить не более 4 вариантов. Сохраняем первые 4.")
        messages_list = messages_list[:4]
    
    cur_commands[command_name] = {
        "command": command_name,
        "description": description,
        "messages": messages_list
    }
    
    save_custom_commands(chat_id, list(cur_commands.values()))
    
    await message.answer(
        f"🎉 Команда <code>{command_name}</code> успешно создана!\n"
        f"📖 Описание: {description}\n"
        f"💬 Варианты сообщений:\n" + "\n".join(f"• {msg}" for msg in messages_list), parse_mode=ParseMode.HTML)
    await state.clear()

@rp_router.message(Command("rp_remove"))
async def cmd_rp_remove(message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if message.chat.type == "private" or message.chat.type == "channel":
        await message.reply("Эта команда доступна только в группах/супергруппах")
        return

    if not db.has_permission(user_id, 2):
        await message.reply("У вас недостаточно прав для выполнению этой команды")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("Использование: /rp_remove <команда>")
        return

    command_name = parts[1].strip()

    cur_commands = get_chat_commands(chat_id)

    if command_name not in cur_commands:
        await message.reply("Такой команды не существует.")
        return

    del cur_commands[command_name]
    save_custom_commands(chat_id, list(cur_commands.values()))
    await message.reply(f"Команда {command_name} успешно удалена!")
