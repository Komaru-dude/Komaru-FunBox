import os
import traceback

import aiohttp
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import RANK_TO_LEVEL, Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils import aio_tools

rights_router = Router()


class SetRankStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_rank = State()


@rights_router.message(Command("set_rank"), CooldownFilter("ranks", 7))
async def cmd_set_rank(message: Message, state: FSMContext, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        if message.chat.type in ["private", "channel"]:
            await message.reply("❌ Эта команда доступна только в группах/супергруппах")
            return

        owner_id = await aio_tools.get_chat_owner_id(bot, chat_id)

        if not (await db.has_permission(user_id, chat_id, 2) or owner_id == user_id):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        await state.set_state(SetRankStates.waiting_for_username)
        await message.reply(
            "✅ Отлично! Начнём!\n\n✍️ Введите имя пользователя (юзернейм или айди)."
        )
    except Exception:
        await aio_tools.error_report(message, bot, "set_rank", traceback.format_exc())


@rights_router.message(SetRankStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext, db: Database):
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
                mention = text[entity.offset : entity.offset + entity.length].lstrip(
                    "@"
                )
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(
                            f"http://127.0.0.1:8001/user/{mention}"
                        ) as resp:
                            data = await resp.json()
                            user_id = data.get("user_id")
                            error_msg = data.get("error")
                    except Exception as e:
                        error_msg = f"Ошибка API: {str(e)}"
                break

    if not user_id and not error_msg:
        if text.isdigit():
            user_id = int(text)
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        f"http://127.0.0.1:8001/username/{chat_id}/{user_id}"
                    ) as resp:
                        if (await resp.json()).get("error"):
                            error_msg = "Пользователь не найден"
                except Exception as e:
                    error_msg = f"Ошибка API: {str(e)}"
        else:
            username = text.lstrip("@")
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        f"http://127.0.0.1:8001/user/{username}"
                    ) as resp:
                        data = await resp.json()
                        user_id = data.get("user_id")
                        error_msg = data.get("error")
                except Exception as e:
                    error_msg = f"Ошибка API: {str(e)}"

    if error_msg or not user_id:
        await message.reply(f"Не удалось найти пользователя, ошибка {error_msg}")
        return await state.clear()

    if not await db.user_exists(user_id, chat_id):
        await db.add_user(user_id, chat_id)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"http://127.0.0.1:8001/first_name/{chat_id}/{user_id}"
            ) as resp:
                data = await resp.json()
                first_name = data.get("first_name", "Пользователь")
        except:
            first_name = "Пользователь"

    builder = InlineKeyboardBuilder()
    for rank in ["Участник", "Модератор", "Администратор"]:
        builder.button(text=rank, callback_data=f"setrank_{rank}")

    if message.from_user.id == int(os.getenv("OWNER_ID")):
        builder.button(text=rank, callback_data=f"setrank_Персонал")

    builder.adjust(1)

    await state.update_data(target_user_id=user_id, first_name=first_name)
    await message.reply(
        f"Выберите новый ранг для {first_name}:", reply_markup=builder.as_markup()
    )
    await state.set_state(SetRankStates.waiting_for_rank)


@rights_router.callback_query(SetRankStates.waiting_for_rank)
async def process_rank_selection(
    callback: CallbackQuery, state: FSMContext, bot: Bot, db: Database
):
    data = await state.get_data()
    target_user_id = data["target_user_id"]
    first_name = data["first_name"]
    selected_rank = callback.data.split("_")[1]

    current_user = callback.from_user
    user_id = current_user.id

    owner_id = await aio_tools.get_chat_owner_id(bot, callback.message.chat.id)
    is_chat_owner = user_id == owner_id

    owner_bot_id = int(os.getenv("OWNER_ID"))
    is_global_owner = user_id == owner_bot_id

    user_rank = await db.get_user_rank(user_id, callback.message.chat.id)
    user_level = RANK_TO_LEVEL.get(user_rank, 0)
    required_level = RANK_TO_LEVEL.get(selected_rank, 999)

    if not (is_chat_owner or is_global_owner) and user_level < required_level:
        await callback.answer(
            "❌ Недостаточно прав для установки этого ранга!", show_alert=True
        )
        return

    try:
        await db.set_rank(target_user_id, callback.message.chat.id, selected_rank)
        await callback.message.edit_text(
            f"✅ Ранг пользователя {first_name} успешно изменён на: {selected_rank}"
        )
    except Exception as e:
        await callback.message.edit_text("❌ Ошибка при обновлении ранга")
        await bot.send_message(owner_bot_id, f"Ошибка в /set_rank: {str(e)}")

    await state.clear()
    await callback.answer()
