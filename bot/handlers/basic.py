import re
import time
import traceback
from urllib.parse import quote

import aiohttp
import psutil
from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import update_cache

base_router = Router()
BASE_COMMANDS_URL = "https://komaru-dude.github.io/Komaru-FunBox/docs/commands"
BASE_MODULES_URL = "https://komaru-dude.github.io/Komaru-FunBox/docs/modules"
# Списки хранения данных для /status
cpu_loads = []
memory_loads = []
start_time = time.time()


@base_router.message(Command("start"), CooldownFilter("start", 5))
async def cmd_start(message: Message):
    await message.reply(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n"
        "🤖 Это развлекательный и модерационный бот.\n"
        "❔ Если хочешь узнать более подробную информацию о командах, напиши <code>/help.</code>\n\n"
        "👤 Владелец бота: @komaru_dude\n"
        "📚 Гайд по настройке бота: https://komaru-dude.github.io/Komaru-FunBox/docs/setup/faststart\n"
        "📰 Новостной канал бота: @komaru_funbox\n"
        "🧑‍💻 Исходный код бота: https://github.com/Komaru-dude/Komaru-FunBox\n\n"
        "🎩 <b>Приятного</b> использования!",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@base_router.message(Command("status"), CooldownFilter("status", 15))
async def cmd_status(message: Message, bot: Bot, db: Database):
    try:
        global start_time

        ping_start_time = time.monotonic()
        sent_message = await message.reply("⏳")
        end_time = time.monotonic()
        ping = (end_time - ping_start_time) * 1000

        current_time = time.time()
        uptime_seconds = int(current_time - start_time)

        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent
        cpu_loads.append((current_time, cpu_percent))
        memory_loads.append((current_time, memory_percent))
        five_minutes_ago = current_time - 300
        cpu_loads[:] = [(t, load) for t, load in cpu_loads if t >= five_minutes_ago]
        memory_loads[:] = [
            (t, load) for t, load in memory_loads if t >= five_minutes_ago
        ]
        avg_cpu_load = (
            sum(load for _, load in cpu_loads) / len(cpu_loads) if cpu_loads else 0
        )
        avg_memory_load = (
            sum(load for _, load in memory_loads) / len(memory_loads)
            if memory_loads
            else 0
        )

        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}д {hours}ч {minutes}м {seconds}с"

        try:
            version = update_cache.get("current_ver", "unknown")
            commit = update_cache.get("current_commit", "unknown")
            branch = update_cache.get("branch", "unknown")
            if update_cache.get("has_update", "unknown"):
                update_status = f"⚡️ Доступно обновление: {update_cache.get("latest_ver", "unknown")}@{update_cache.get("update_commit", "unknown")}"
            else:
                update_status = f"😉 Обновлений нет"

        except:
            version = "unknown"
            commit = "unknown"
            branch = "unknown"
            update_status = "unknown"

        day_count, week_count = await db.get_use_stats()

        status_message = (
            f"<blockquote><b>🍕 Komaru FunBox</b>\n"
            f"🧬 Версия: <code>{version}@{commit}</code>\n"
            f"🌿 Ветка: <b>{branch}</b>\n"
            f"{update_status}\n"
            f"⏳ Пинг: {int(ping)} мс\n"
            f"🚀 Аптайм: {uptime_str}\n"
            f"🔺 Использований сегодня: {day_count}\n"
            f"♦️ Использований за неделю: {week_count}\n"
            f"📊 CPU (5 мин): {avg_cpu_load:.1f}%\n"
            f"📊 RAM (5 мин): {avg_memory_load:.1f}%</blockquote>"
        )

        await sent_message.edit_text(status_message, parse_mode=ParseMode.HTML)

    except Exception:
        await error_report(message, bot, "status", traceback.format_exc())


@base_router.message(Command("cancel"), CooldownFilter("cancel", 5))
async def cmd_cancel(message: Message, bot: Bot, state: FSMContext):
    try:
        current_state = await state.get_state()
        if current_state is None:
            await message.reply("📛 Нечего отменять")
        else:
            await state.clear()
            await message.reply("❌ Отменено")
    except Exception:
        await error_report(message, bot, "cancel", traceback.format_exc())


@base_router.message(Command("set_name"), CooldownFilter("set_name", 1200))
async def cmd_set_name(message: Message, bot: Bot, db: Database):
    try:
        if message.reply_to_message:
            await message.reply(
                "📛 Эта команда предназначена для изменения своего имени."
            )

        user = message.from_user
        parts = message.text.split(maxsplit=1)
        new_name = parts[1] if len(parts) > 1 else None

        if not new_name:
            await message.reply("📛 Укажите новое имя после команды /set_name")
            return

        if not (5 <= len(new_name) <= 32):
            await message.reply("📛 Имя должно быть от 5 до 32 символов.")
            return

        if not re.fullmatch(r"[A-Za-zА-Яа-яЁё\s\-]+", new_name):
            await message.reply(
                "📛 Имя может содержать только русские и английские буквы, пробелы и дефисы."
            )
            return

        await db.set_global_user_param(user.id, "name", new_name)
        await message.reply(f"✅ Ваше имя в боте изменено на {new_name}")

    except Exception:
        await error_report(message, bot, "set_name", traceback.format_exc())


async def check_wiki_page(url):
    async with aiohttp.ClientSession() as session:
        async with session.head(url) as response:
            return response.status == 200 or response.status == 301


async def find_wiki_page(name: str) -> str | None:
    encoded_name = quote(name)
    url_commands = f"{BASE_COMMANDS_URL}/{encoded_name}"
    url_modules = f"{BASE_MODULES_URL}/{encoded_name}"
    if await check_wiki_page(url_commands):
        return url_commands
    elif await check_wiki_page(url_modules):
        return url_modules
    return None


@base_router.message(Command("help"), CooldownFilter("help", 10))
async def cmd_help(message: Message, bot: Bot):
    parts = message.text.strip().split(maxsplit=1)

    if len(parts) == 1:
        await message.reply(
            f"Полный список команд и их описания доступны в вики:\n{BASE_COMMANDS_URL}/",
            disable_web_page_preview=True,
        )
    else:
        argument = parts[1].lower()
        found_url = await find_wiki_page(argument)
        if found_url:
            await message.reply(
                f"Подробная информация о '{argument}':\n{found_url}",
                disable_web_page_preview=True,
            )
        else:
            await message.reply(
                f"'{argument}' не найдено в вики.\nПолный список команд: {BASE_COMMANDS_URL}/\nСписок модулей: {BASE_MODULES_URL}/",
                disable_web_page_preview=True,
            )
