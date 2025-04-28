import subprocess
import time
import traceback
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import db
from bot.utils.aio_tools import fetch_user_data, error_report

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
    except Exception:
        await error_report(message, bot, "restart", traceback.format_exc())


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
