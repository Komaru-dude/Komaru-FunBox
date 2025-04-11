import aiohttp, os
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import db
from bot.db import RANK_TO_LEVEL

mods_router = Router()

class SetRankStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_rank = State()

@mods_router.message(Command("set_rank"))
async def cmd_set_rank(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not db.has_permission(user_id, 2):
        await message.reply("У вас недостаточно прав для выполнения этой команды.")
        return
    
    await state.set_state(SetRankStates.waiting_for_username)
    await message.reply("✅ Отлично! Начнём!\n\n✍️ Введите имя пользователя (реплай, юзернейм, айди).")

@mods_router.message(SetRankStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext, bot: Bot):
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
        await message.reply(error_msg or "Не удалось найти пользователя")
        return await state.clear()

    if not db.user_exists(user_id):
        db.add_user(user_id)

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
async def process_rank_selection(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    target_user_id = data['target_user_id']
    first_name = data['first_name']
    selected_rank = callback.data.split('_')[1]

    current_user = callback.from_user
    is_owner = str(current_user.id) == os.getenv("OWNER_ID")
    
    if not is_owner:
        user_rank = db.get_user_rank(current_user.id)
        user_level = RANK_TO_LEVEL.get(user_rank, 0)
        required_level = RANK_TO_LEVEL[selected_rank]
        
        if user_level < required_level:
            await callback.answer("❌ Недостаточно прав для установки этого ранга!", show_alert=True)
            return

    if db.set_rank(target_user_id, selected_rank):
        await callback.message.edit_text(
            f"✅ Ранг пользователя {first_name} успешно изменён на: {selected_rank}"
        )
    else:
        await callback.message.edit_text("❌ Ошибка при обновлении ранга")

    await state.clear()
    await callback.answer()