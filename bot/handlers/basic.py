import time
import psutil
import traceback

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from bot.database import Database
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import update_cache

base_router = Router()
# Списки хранения данных для /status
cpu_loads = []
memory_loads = []
start_time = time.time()


@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        f"👋 Привет, {message.from_user.first_name}!\n"
        "🤖 Это развлекательный и модерационный бот.\n"
        "❔ Если хочешь узнать более подробную информацию о командах, напиши /help.\n\n"
        "👤 Владелец бота: @komaru_dude\n"
        "📚 Гайд по настройке бота: https://komaru-dude.github.io/Komaru-FunBox/docs/setup/faststart\n"
        "📰 Новостной канал бота: @komaru_funbox\n"
        "🧑‍💻 Исходный код бота: https://github.com/Komaru-dude/Komaru-FunBox\n\n"
        "🎩 Приятного использования!",
        disable_web_page_preview=True,
    )


@base_router.message(Command("status"))
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
                update_status = f"⚡️ Доступно обновление: {update_cache.get("latest_ver", "unknown")}@{update_cache.get("latest_commit", "unknown")}"
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


@base_router.message(Command("cancel"))
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
