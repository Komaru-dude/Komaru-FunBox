import aiohttp, os, subprocess, traceback, uuid
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions
from bot import db
from bot.utils.aio_tools import fetch_json
from datetime import datetime, timedelta

mods_router = Router()
API_URL = "http://127.0.0.1:8001"
        
def parse_time(time_str):
    """Парсит время из строки формата 3h, 3m или 3d"""
    try:
        unit = time_str[-1]
        amount = int(time_str[:-1])
        if unit == 'h':
            return timedelta(hours=amount)
        elif unit == 'm':
            return timedelta(minutes=amount)
        elif unit == 'd':
            return timedelta(days=amount)
        else:
            return None
    except (ValueError, IndexError):
        return None
    
def format_duration(duration: timedelta) -> str:
    if not duration:
        return "навсегда"
    
    total_seconds = int(duration.total_seconds())
    periods = [
        ('года', 60*60*24*365),
        ('месяца', 60*60*24*30),
        ('дней', 60*60*24),
        ('часов', 60*60),
        ('минут', 60),
        ('секунд', 1)
    ]
    
    parts = []
    for period_name, period_seconds in periods:
        if total_seconds >= period_seconds:
            period_value = total_seconds // period_seconds
            total_seconds %= period_seconds
            parts.append(f"{period_value} {period_name}")
    
    return " ".join(parts[:2]) if parts else "менее минуты"

def parse_command(text: str) -> dict:
    parts = text.split(maxsplit=3)
    return {
        'duration': parts[1] if len(parts) > 1 else None,
        'reason': parts[2] if len(parts) > 2 else 'Без причины'
    }

async def get_target_user(message: Message, bot: Bot):
    if message.reply_to_message:
        return message.reply_to_message.from_user
    
    parts = message.text.split()
    if len(parts) < 2:
        raise ValueError("Не указан пользователь")
    
    target = parts[1]
    if target.startswith('@'):
        user_data = await fetch_json(f"http://127.0.0.1:8001/user/{target}")
        return type('User', (), {'id': user_data['user_id']})
    
    if target.isdigit():
        return type('User', (), {'id': int(target)})
    
    raise ValueError("Неверный формат идентификатора")

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

@mods_router.message(Command("warn"))
async def warn_cmd(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    parts = message.text.split(' ', 2)

    if not db.has_permission(user_id, chat_id, 2):
        return await message.reply("⛔ Недостаточно прав для выполнения команды")
    
    try:
        # Определение цели
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            reason = parts[2] if len(parts) > 2 else "Без причины"
        else:
            if len(parts) < 2:
                return await message.reply("❌ Укажите пользователя: /warn @юзернейм/id [причина]")
            
            target = parts[1]
            reason = parts[2] if len(parts) > 2 else "Без причины"
            
            if target.startswith('@'):
                user_data = await fetch_json(f"http://127.0.0.1:8001/user/{target}")
                target_user = type('User', (), {'id': user_data['user_id']})
            elif target.isdigit():
                target_user = type('User', (), {'id': int(target)})
            else:
                return await message.reply("❌ Неверный формат идентификатора")

        # Обновление предупреждений
        db.update_user_warns(target_user.id, chat_id, reason)
        user_data = db.get_user_data(target_user.id, chat_id)
        
        # Проверка лимита
        if user_data[2] >= user_data[9]:
            until_date = datetime.now() + timedelta(hours=24)
            await bot.restrict_chat_member(
                chat_id,
                target_user.id,
                ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            
            # Обновление данных
            db.update_user_mutes(target_user.id, chat_id, "Превышение лимита предупреждений")
            db.update_user_warn_limit(target_user.id, chat_id, 3)
            db.update_rep(user_id, chat_id, "manual_rem", 15)
            
            await message.reply(
                f"🔇 Пользователь {target_user.id} получил мьют до {until_date:%d.%m.%Y %H:%M}\n"
                f"📝 Причина: превышение лимита предупреждений ({user_data[2]}/{user_data[9]})"
            )
        else:
            await message.reply(
                f"⚠ {target_user.id} получил предупреждение\n"
                f"📝 Причина: {reason}\n"
                f"🔢 {user_data[2]+1}/{user_data[9]}"
            )

    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        await bot.send_message(os.getenv("OWNER_ID"), f"⚠ Ошибка в /warn: {traceback.format_exc()}")

@mods_router.message(Command("mute"))
async def cmd_mute(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not db.has_permission(user_id, chat_id, 2):
        return await message.reply("⛔ Недостаточно прав")

    try:
        # Парсинг аргументов
        args = parse_command(message.text)
        target_user = await get_target_user(message, bot)
        duration = parse_time(args.get('duration', '24h')) 
        reason = args.get('reason', 'Без причины')

        # Применение мута
        until_date = datetime.now() + duration if duration else None
        await bot.restrict_chat_member(
            chat_id,
            target_user.id,
            ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        
        # Обновление БД
        db.update_user_mutes(target_user.id, chat_id, reason)
        db.update_rep(user_id, chat_id, "manual_rem", 10)
        
        await message.reply(
            f"🔇 {target_user.id} замьючен на {format_duration(duration)}\n"
            f"📝 Причина: {reason}"
        )

    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        await bot.send_message(os.getenv("OWNER_ID"), f"⚠ Ошибка в /mute: {traceback.format_exc()}")

@mods_router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not db.has_permission(user_id, chat_id, 2):
        return await message.reply("⛔ Недостаточно прав")

    try:
        args = parse_command(message.text)
        target_user = await get_target_user(message, bot)
        duration = parse_time(args.get('duration', 'forever'))
        reason = args.get('reason', 'Без причины')

        # Применение бана
        until_date = datetime.now() + duration if duration else None
        await bot.ban_chat_member(chat_id, target_user.id, until_date=until_date)
        
        # Обновление БД
        db.update_user_bans(target_user.id, chat_id, reason)
        db.update_rep(user_id, chat_id, "manual_rem", 15)
        
        await message.reply(
            f"🔨 {target_user.id} забанен на {format_duration(duration)}\n"
            f"📝 Причина: {reason}"
        )

    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        await bot.send_message(os.getenv("OWNER_ID"), f"⚠ Ошибка в /ban: {traceback.format_exc()}")

@mods_router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not db.has_permission(user_id, chat_id, 2):
        return await message.reply("⛔ Недостаточно прав")

    try:
        target_user = await get_target_user(message, bot)
        
        # Снятие мута
        await bot.restrict_chat_member(
            chat_id,
            target_user.id,
            ChatPermissions(can_send_messages=True),
            until_date=datetime.now()
        )
        
        await message.reply(f"🔔 {target_user.id} размьючен")

    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        await bot.send_message(os.getenv("OWNER_ID"), f"⚠ Ошибка в /unmute: {traceback.format_exc()}")

@mods_router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not db.has_permission(user_id, chat_id, 2):
        return await message.reply("⛔ Недостаточно прав")

    try:
        target_user = await get_target_user(message, bot)
        
        # Снятие бана
        await bot.unban_chat_member(chat_id, target_user.id)
        await message.reply(f"🎉 {target_user.id} разбанен")

    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        await bot.send_message(os.getenv("OWNER_ID"), f"⚠ Ошибка в /unban: {traceback.format_exc()}")

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

@mods_router.message(Command("repadd"))
async def cmd_repadd(message: Message):
    user_id = message.from_user.id
    text = message.text
    if not db.has_permission(user_id, 2):
        await message.reply("У вас нет прав для выполнения этой команды.")
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
    
