import os
import time
import psutil
import asyncio
import aiohttp
import json
import subprocess
import traceback
import uuid
from pathlib import Path
from urllib.parse import urlparse
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from bot import database
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import CACHE_DIR, update_cache

base_router = Router()
models_path = database.BASE_DIR / "data" / "models.json"
db = database.Database()
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
async def cmd_status(message: Message, bot: Bot):
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


def get_service_name() -> str:
    folder_name = Path(__path__).parent.parent.parent.name
    if "test" in folder_name:
        return "komaru-funbox_test.service"
    else:
        return "komaru-funbox.service"

SERVICE_NAME = get_service_name()

@base_router.message(Command("restart"))
async def cmd_restart(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not await db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ Эта команда только для персонала.")
        return
    await message.answer("Перезапускаюсь... 🔄")

    try:
        subprocess.Popen(["sudo", "systemctl", "restart", SERVICE_NAME])
    except Exception:
        await error_report(message, bot, "restart", traceback.format_exc())

@base_router.message(Command("update"))
async def cmd_update(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not await db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ Эта команда только для персонала.")
        return

    update_msg = await message.reply("🔄 Обновляюсь...")

    try:
        branch = (
            subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            .decode()
            .strip()
        )
        commit = (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
            .decode()
            .strip()
        )
        repo_url = "https://github.com/Komaru-dude/Komaru-FunBox"
    except Exception:
        branch = commit = "unknown"
        repo_url = ""

    repo_path = urlparse(repo_url).path.strip("/")
    if not repo_path:
        raise ValueError("Неверный формат URL")

    owner, repo = repo_path.split("/")[:2]
    repo = repo.replace(".git", "")

    headers = {"User-Agent": "KomaruBot/1.0"}
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}",
            headers=headers,
        ) as resp:
            response_body = await resp.text()
            if resp.status == 200:
                data = await resp.json()
                latest_commit = data["commit"]["sha"][:7]
                if latest_commit == commit:
                    return await update_msg.edit_text("☃️ Версия актуальна")
            else:
                return await update_msg.edit_text(
                    f"⚠️ Ошибка API: {resp.status}\nТело ответа: {response_body}"
                )

    try:
        os.remove(models_path)
    except FileNotFoundError:
        await update_msg.edit_text("⚠️ Не удалось удалить кэш загруженных моделей")

    try:
        subprocess.Popen(["sudo", "systemctl", "restart", SERVICE_NAME])
    except Exception:
        await error_report(message, bot, "update", traceback.format_exc())

@base_router.message(Command("logs"))
async def cmd_send_logs(message: Message, bot: Bot):
    try:
        random_log_name = f"{uuid.uuid4()}.log"
        out_path = CACHE_DIR / random_log_name

        if not await db.has_permission(message.from_user.id, message.chat.id, 4):
            await message.reply("❌ Эта команда только для персонала.")
            return

        out_path.parent.mkdir(exist_ok=True, parents=True)

        process = await asyncio.create_subprocess_exec(
            "journalctl",
            "--no-pager",
            "-u",
            SERVICE_NAME,
            "-n",
            "80",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Ошибка выполнения команды: {stderr.decode()}")

        with open(out_path, "wb") as f:
            f.write(stdout)

        await message.reply_document(FSInputFile(out_path), caption="📝 Вот ваши логи:")
    except Exception:
        await error_report(message, bot, "logs", traceback.format_exc())
    finally:
        if out_path.exists():
            out_path.unlink()


@base_router.message(Command("logs"))
async def cmd_send_logs(message: Message, bot: Bot):
    try:
        random_log_name = f"{uuid.uuid4()}.log"
        out_path = CACHE_DIR / random_log_name

        if not await db.has_permission(message.from_user.id, message.chat.id, 4):
            await message.reply("❌ Эта команда только для персонала.")
            return

        out_path.parent.mkdir(exist_ok=True, parents=True)

        process = await asyncio.create_subprocess_exec(
            "journalctl",
            "--no-pager",
            "-u",
            "komaru-funbox.service",
            "-n",
            "80",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Ошибка выполнения команды: {stderr.decode()}")

        with open(out_path, "wb") as f:
            f.write(stdout)

        await message.reply_document(FSInputFile(out_path), caption="📝 Вот ваши логи:")
    except Exception:
        await error_report(message, bot, "logs", traceback.format_exc())
    finally:
        if out_path.exists():
            out_path.unlink()


@base_router.message(Command("reset_cooldown"))
async def cmd_reset_cooldown(message: Message, bot: Bot):
    try:
        split_text = message.text.split()

        if not await db.has_permission(message.from_user.id, message.chat.id, 4):
            await message.reply("❌ Эта команда только для персонала.")
            return

        if len(split_text) < 3:
            await message.reply(
                "❌ Некорректный синтаксис!\nИспользуйте: <code>/reset_cooldown user_id command_name</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            target_user_id = int(split_text[1])
        except ValueError:
            await message.reply("❌ user_id должен быть числом.")
            return
        target_command = split_text[2]

        await db.reset_cooldown(target_user_id, target_command)
        await message.reply("✅ Успешно сброшено")
    except Exception:
        await error_report(message, bot, "reset_cooldown", traceback.format_exc())
