import aiohttp
import os
import traceback
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot import db
from bot.db import RANK_TO_LEVEL
from bot.utils import aio_tools

rights_router = Router()
API_URL = "http://127.0.0.1:8001"


class SetRankStates(StatesGroup):
    waiting_for_username = State()
    waiting_for_rank = State()


@rights_router.message(Command("set_rank"))
async def cmd_set_rank(message: Message, state: FSMContext, bot: Bot):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        if message.chat.type in ["private", "channel"]:
            await message.reply("❌ Эта команда доступна только в группах/супергруппах")
            return

        owner_id = await aio_tools.get_chat_owner_id(bot, chat_id)

        if not (db.has_permission(user_id, chat_id, 2) or owner_id == user_id):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        if db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        await state.set_state(SetRankStates.waiting_for_username)
        await message.reply(
            "✅ Отлично! Начнём!\n\n✍️ Введите имя пользователя (реплай, юзернейм, айди)."
        )
    except Exception:
        await aio_tools.error_report(message, bot, "set_rank", traceback.format_exc())


@rights_router.message(SetRankStates.waiting_for_username)
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

    if not db.user_exists(user_id, chat_id):
        db.add_user(user_id, chat_id)

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

    builder.adjust(1)

    await state.update_data(target_user_id=user_id, first_name=first_name)
    await message.reply(
        f"Выберите новый ранг для {first_name}:", reply_markup=builder.as_markup()
    )
    await state.set_state(SetRankStates.waiting_for_rank)


@rights_router.callback_query(SetRankStates.waiting_for_rank)
async def process_rank_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
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

    user_rank = db.get_user_rank(user_id, callback.message.chat.id)
    user_level = RANK_TO_LEVEL.get(user_rank, 0)
    required_level = RANK_TO_LEVEL.get(selected_rank, 999)

    if not (is_chat_owner or is_global_owner) and user_level < required_level:
        await callback.answer(
            "❌ Недостаточно прав для установки этого ранга!", show_alert=True
        )
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


@rights_router.message(Command("ban_media"))
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
                data = await aio_tools.fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = data["user_id"]
                    name_data = await aio_tools.fetch_json(
                        f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                    )
                    first_name = name_data.get("first_name", "Неизвестный")
                else:
                    await message.reply(
                        f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                    )
                    return

            except Exception:
                await aio_tools.error_report(
                    message, bot, "ban_media", traceback.format_exc()
                )
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = split_text[1]
            try:
                data = await aio_tools.fetch_json(
                    f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                )
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply(
                "Укажите пользователя через реплай, @username или айди."
            )
            return

    if db.is_user_mediabanned(target_id):
        await message.reply("❌ Пользователь уже заблокирован")
        return

    try:
        db.mediaban_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был заблокирован")
    except Exception as e:
        await aio_tools.error_report(message, bot, "ban_media", traceback.format_exc())


@rights_router.message(Command("unban_media"))
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
                data = await aio_tools.fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = data["user_id"]
                    name_data = await aio_tools.fetch_json(
                        f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                    )
                    first_name = name_data.get("first_name", "Неизвестный")
                else:
                    await message.reply(
                        f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                    )
                    return

            except Exception:
                await aio_tools.error_report(
                    message, bot, "unban_media", traceback.format_exc()
                )
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = split_text[1]
            try:
                data = await aio_tools.fetch_json(
                    f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                )
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply(
                "Укажите пользователя через реплай, @username или айди."
            )
            return

    if not db.is_user_mediabanned(target_id):
        await message.reply("❌ Пользователь уже разблокирован")
        return

    try:
        db.mediaunban_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был разблокирован")
    except Exception as e:
        await aio_tools.error_report(
            message, bot, "unban_media", traceback.format_exc()
        )
