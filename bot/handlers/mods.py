import time
import traceback
from datetime import datetime, timedelta
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import db
from bot.utils.aio_tools import (
    fetch_user_data,
    error_report,
    get_user_id,
)

mods_router = Router()
API_URL = "http://127.0.0.1:8001"


def parse_time(time_str: str) -> timedelta | None:
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    seconds = 0
    number = ""
    for char in time_str:
        if char.isdigit():
            number += char
        elif char in units:
            if number:
                seconds += int(number) * units[char]
                number = ""
        else:
            return None
    return timedelta(seconds=seconds) if seconds else None


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
        await error_report(message, bot, "enable", traceback.format_exc())


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
    except Exception:
        await error_report(message, bot, "disable", traceback.format_exc())


@mods_router.message(Command("history"))
async def cmd_history(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        history = db.get_history(user_id, message.chat.id)

        if not history:
            await message.reply("У вас пока нет наказаний.")
            return

        history_text = ""
        for i, entry in enumerate(history, start=1):
            punishment_type = entry["type"]
            reason = entry.get("reason", "Без причины")
            history_text += (
                f"{i}. {punishment_type.capitalize()} - Причина: {reason}.\n"
            )

        warns_count = len(history)
        response = (
            f"Всего наказаний: {warns_count}\n" f"История наказаний:\n{history_text}"
        )
        await message.reply(response)

    except Exception:
        await error_report(message, bot, "history", traceback.format_exc())


@mods_router.message(Command("warn"))
async def cmd_warn(message: Message, bot: Bot):
    command = "warn"
    try:
        split_text = message.text.split(maxsplit=3)
        chat_id = message.chat.id
        if not db.has_permission(message.from_user.id, chat_id, 1):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        if not db.is_feature_enabled(chat_id, "warn"):
            await message.reply("❌ Функция отключена.")
            return

        if not message.reply_to_message and len(split_text) < 2:
            await message.reply(
                "❌ Некорректный синтаксис: /warn реплай/@username/ID причина"
            )
            return

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            target_first_name = message.reply_to_message.from_user.first_name
            reason = split_text[1] if len(split_text) >= 2 else "Не указана"
        elif split_text[1].startswith("@"):
            username = split_text[1].lstrip("@")
            data = await fetch_user_data(username=username, chat_id=chat_id)
            if "error" in data:
                await error_report(message, bot, command, data["error"])
                return
            target_id = data["user_id"]
            target_first_name = data["first_name"]
            reason = split_text[2] if len(split_text) >= 3 else "Не указана"
        elif split_text[1].isdigit():
            target_id = split_text[1]
            data = await fetch_user_data(user_id=target_id, chat_id=chat_id)
            target_first_name = data["first_name"]
            reason = split_text[2] if len(split_text) >= 3 else "Не указана"
        else:
            await error_report(
                message, bot, command, "Не выявленная ошибка синтаксиса."
            )

        if target_id == message.from_user.id:
            await message.reply("❌ Зачем предупреждать самого себя?")
            return

        user_data = db.get_user_data(target_id, chat_id)
        target_user_link = f'<a href="tg://user?id={target_id}">{target_first_name}</a>'
        mod_link = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'

        await message.reply(
            f"✏️ Пользователю {target_user_link} вынесено предупреждение!\nМодератор: {mod_link}\nПричина: {reason}\nКол-во варнов: {user_data[2]}/{user_data[9]}",
            parse_mode=ParseMode.HTML,
        )
        if user_data[2] >= user_data[9]:
            until_date = int(time.time()) + 2 * 3600

            await message.answer(
                f"🔇 Пользователь {target_user_link} был замьючен!\nМодератор: Авто-мод\nПричина: Превышение лимита предупреждений",
                parse_mode=ParseMode.HTML,
            )
            db.update_user_warn_limit(target_id, chat_id, 3)
            db.update_user_warns(target_id, chat_id, reason)
            await bot.restrict_chat_member(
                chat_id,
                target_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
        else:
            db.update_user_warns(target_id, chat_id, reason)

    except TelegramBadRequest as e:
        await message.reply(f"⚠️ Возникла ошибка телеграмма: {e}")
    except Exception:
        await error_report(message, bot, command, traceback.format_exc())
        return


@mods_router.message(Command("info"))
async def cmd_info(message: Message, bot: Bot):
    try:
        chat_id = message.chat.id
        split_text = message.text.split()
        error = None
        if len(split_text) < 2:
            user_id = message.from_user.id
        else:
            user_id, error = await get_user_id(message)

        if error:
            return await message.reply(f"❌ {error}")

        user_info = await fetch_user_data(user_id=user_id, chat_id=chat_id)
        if "error" in user_info:
            return await message.reply(f"❌ {user_info['error']}")

        user_data = db.get_user_data(user_info["user_id"], chat_id)
        if not user_data:
            return await message.reply("❌ Пользователь не найден в базе данных")

        profile_link = f"tg://user?id={user_info['user_id']}"
        clickable_name = f'<a href="{profile_link}">{user_info["first_name"]}</a>'

        info_text = (
            f"👤 Информация о {clickable_name}\n"
            f"🆔 ID: {user_info['user_id']}\n"
            f"📊 Статистика:\n"
            f"⚠ Предупреждения: {user_data[2]}/{user_data[9]}\n"
            f"🔇 Мьюты: {user_data[4]}\n"
            f"🔨 Баны: {user_data[3]}\n"
            f"💎 Репутация: {user_data[5]}\n"
            f"📨 Сообщений: {user_data[7]}\n"
            f"🏅 Ранг: {user_data[6]}\n"
        )

        await message.reply(info_text, parse_mode=ParseMode.HTML)

    except Exception:
        await error_report(message, bot, "info", traceback.format_exc())


@mods_router.message(Command("mute"))
async def cmd_mute(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        parts = message.text.split(maxsplit=3)

        if not db.has_permission(user_id, chat_id, 2):
            await message.reply("❌ У вас нет прав для этой команды")
            return

        target_user_id, error_msg = await get_user_id(message)
        if not target_user_id:
            await message.reply(f"❌ {error_msg}")
            return

        if message.reply_to_message:
            time_arg = parts[1] if len(parts) > 1 else None
            reason = parts[2] if len(parts) > 2 else "Без причины"
            await message.reply_to_message.delete()
        else:
            time_arg = parts[2] if len(parts) > 2 else None
            reason = parts[3] if len(parts) > 3 else "Без причины"

        duration = parse_time(time_arg) if time_arg else None
        until_date = datetime.now() + duration if duration else None

        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )

        db.add_user(target_user_id, chat_id)
        db.update_user_mutes(target_user_id, chat_id, reason)
        db.update_rep(target_user_id, chat_id, "manual_rem", 10)

        time_str = until_date.strftime("%Y-%m-%d %H:%M") if until_date else "навсегда"
        await message.reply(
            f"🔇 Пользователь <b>{target_user_id}</b> замьючен до {time_str}\n"
            f"Причина: {reason}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await error_report(message, bot, "mute", str(e))


@mods_router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        parts = message.text.split(maxsplit=3)

        if not db.has_permission(user_id, chat_id, 2):
            await message.reply("❌ Недостаточно прав")
            return

        target_user_id, error_msg = await get_user_id(message)
        if not target_user_id:
            await message.reply(f"❌ {error_msg}")
            return

        if message.reply_to_message:
            time_arg = parts[1] if len(parts) > 1 else None
            reason = parts[2] if len(parts) > 2 else "Без причины"
            await message.reply_to_message.delete()
        else:
            time_arg = parts[2] if len(parts) > 2 else None
            reason = parts[3] if len(parts) > 3 else "Без причины"

        duration = parse_time(time_arg) if time_arg else None
        until_date = datetime.now() + duration if duration else None

        await bot.ban_chat_member(chat_id, target_user_id, until_date=until_date)

        db.add_user(target_user_id, chat_id)
        db.update_user_bans(target_user_id, chat_id, reason)
        db.update_rep(target_user_id, chat_id, "manual_rem", 15)

        time_str = until_date.strftime("%Y-%m-%d %H:%M") if until_date else "навсегда"
        await message.reply(
            f"⛔ Пользователь <b>{target_user_id}</b> забанен до {time_str}\n"
            f"Причина: {reason}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await error_report(message, bot, "ban", str(e))


@mods_router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not db.has_permission(user_id, chat_id, 2):
            await message.reply("❌ Недостаточно прав")
            return

        target_user_id, error_msg = await get_user_id(message)
        if not target_user_id:
            await message.reply(f"❌ {error_msg}")
            return

        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
            ),
        )
        await message.reply(
            f"🔄 Пользователь <b>{target_user_id}</b> размьючен",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await error_report(message, bot, "unmute", str(e))


@mods_router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id

        if not db.has_permission(user_id, chat_id, 2):
            await message.reply("❌ Недостаточно прав")
            return

        target_user_id, error_msg = await get_user_id(message)
        if not target_user_id:
            await message.reply(f"❌ {error_msg}")
            return

        await bot.unban_chat_member(chat_id, target_user_id)
        await message.reply(
            f"✅ Пользователь <b>{target_user_id}</b> разбанен",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await error_report(message, bot, "unban", str(e))
