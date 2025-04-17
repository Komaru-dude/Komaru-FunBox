import aiohttp, os, subprocess, uuid
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import db
from bot.db import RANK_TO_LEVEL
from bot.utils import aio_tools

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

class SetRankStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_rank = State()

@mods_router.message(Command("set_rank"))
async def cmd_set_rank(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    owner_id = await aio_tools.get_chat_owner_id(bot, chat_id)

    if not (db.has_permission(user_id, chat_id, 2) or owner_id == user_id):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    
    await state.set_state(SetRankStates.waiting_for_username)
    await message.reply("✅ Отлично! Начнём!\n\n✍️ Введите имя пользователя (реплай, юзернейм, айди).")

@mods_router.message(SetRankStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    chat_id = message.chat.id
    text = message.text
    user_id = None
    error_msg = None

    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                user_id = entity.user.id
                break
            elif entity.type == "mention":
                mention = text[entity.offset:entity.offset+entity.length].lstrip('@')
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f'http://127.0.0.1:8001/user/{mention}') as resp:
                            data = await resp.json()
                            user_id = data.get('user_id')
                            error_msg = data.get('error')
                    except Exception as e:
                        error_msg = f"Ошибка API: {str(e)}"
                break

    if not user_id and not error_msg:
        if text.isdigit():
            user_id = int(text)
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(f'http://127.0.0.1:8001/username/{chat_id}/{user_id}') as resp:
                        if (await resp.json()).get('error'):
                            error_msg = "Пользователь не найден"
                except Exception as e:
                    error_msg = f"Ошибка API: {str(e)}"
        else:
            username = text.lstrip('@')
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(f'http://127.0.0.1:8001/user/{username}') as resp:
                        data = await resp.json()
                        user_id = data.get('user_id')
                        error_msg = data.get('error')
                except Exception as e:
                    error_msg = f"Ошибка API: {str(e)}"

    if error_msg or not user_id:
        await message.reply(f"Не удалось найти пользователя, ошибка {error_msg}")
        return await state.clear()

    if not db.user_exists(user_id, chat_id):
        db.add_user(user_id, chat_id)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f'http://127.0.0.1:8001/first_name/{chat_id}/{user_id}') as resp:
                data = await resp.json()
                first_name = data.get('first_name', 'Пользователь')
        except:
            first_name = "Пользователь"

    builder = InlineKeyboardBuilder()
    for rank in ["Участник", "Модератор", "Администратор"]:
        builder.button(text=rank, callback_data=f"setrank_{rank}")
    
    builder.adjust(1)
    
    await state.update_data(target_user_id=user_id, first_name=first_name)
    await message.reply(
        f"Выберите новый ранг для {first_name}:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(SetRankStates.waiting_for_rank)

@mods_router.callback_query(SetRankStates.waiting_for_rank)
async def process_rank_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id = data['target_user_id']
    first_name = data['first_name']
    selected_rank = callback.data.split('_')[1]

    current_user = callback.from_user
    user_id = current_user.id

    owner_id = await aio_tools.get_chat_owner_id(bot, callback.message.chat.id)
    is_chat_owner = user_id == owner_id

    owner_bot_id = int(os.getenv("OWNER_ID"))
    is_global_owner = user_id == owner_bot_id

    user_rank = db.get_user_rank(user_id, callback.message.chat.id)
    user_level = RANK_TO_LEVEL.get(user_rank, 0)
    required_level = RANK_TO_LEVEL.get(selected_rank, 999)

    if not (is_chat_owner or is_global_owner) and user_level < required_level:
        await callback.answer("❌ Недостаточно прав для установки этого ранга!", show_alert=True)
        return

    try:
        db.set_rank(target_user_id, callback.message.chat.id, selected_rank)
        await callback.message.edit_text(
            f"✅ Ранг пользователя {first_name} успешно изменён на: {selected_rank}"
        )
    except Exception as e:
        await callback.message.edit_text("❌ Ошибка при обновлении ранга")
        await bot.send_message(owner_bot_id, f"Ошибка в /set_rank: {str(e)}")
    
    await state.clear()
    await callback.answer()

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
    
    if not db.has_permission(user_id, chat_id, 1):
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
    
    if not db.has_permission(user_id, chat_id, 1):
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

@mods_router.message(Command("ban"))
async def cmd_ban_user(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    target_id = None
    first_name = None

    if not db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        first_name = message.reply_to_message.from_user.first_name
    else:
        text = message.text
        split_text = text.split(maxsplit=1)

        if len(split_text) > 1 and split_text[1].startswith("@"):
            username = split_text[1][1:]
            try:
                data = await fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = data["user_id"]
                    name_data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                    first_name = name_data.get("first_name", "Неизвестный")
                else:
                    await message.reply(f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}")
                    return

            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = split_text[1]
            try:
                data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply("Укажите пользователя через реплай, @username или айди.")
            return
        
    if db.is_user_banned(target_id):
        await message.reply("❌ Пользователь уже заблокирован")
        return
    
    try:
        db.ban_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был заблокирован")
    except Exception as e:
        report_id = uuid.uuid4()
        await message.reply(f"❌ Не удалось заблокировать\nReport id: {report_id}")
        await bot.send_message(os.getenv("OWNER_ID"), f"Report id: {report_id}\n\nMessage: {message.text}\n\nLogs: {e}")

@mods_router.message(Command("unban"))
async def cmd_unban_user(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    target_id = None
    first_name = None

    if not db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        first_name = message.reply_to_message.from_user.first_name
    else:
        text = message.text
        split_text = text.split(maxsplit=1)

        if len(split_text) > 1 and split_text[1].startswith("@"):
            username = split_text[1][1:]
            try:
                data = await fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = data["user_id"]
                    name_data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                    first_name = name_data.get("first_name", "Неизвестный")
                else:
                    await message.reply(f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}")
                    return

            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = split_text[1]
            try:
                data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply("Укажите пользователя через реплай, @username или айди.")
            return
        
    if not db.is_user_banned(target_id):
        await message.reply("❌ Пользователь уже разблокирован")
        return
    
    try:
        db.unban_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был разблокирован")
    except Exception as e:
        report_id = uuid.uuid4()
        await message.reply(f"❌ Не удалось разблокировать\nReport id: {report_id}")
        await bot.send_message(os.getenv("OWNER_ID"), f"Report id: {report_id}\n\nMessage: {message.text}\n\nLogs: {e}")