import time
import psutil
import aiohttp
import json
import subprocess
import traceback
from pathlib import Path
from urllib.parse import urlparse
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from bot import db
from bot.utils.aio_tools import error_report

base_router = Router()
# Списки хранения данных для /status
cpu_loads = []
memory_loads = []
start_time = time.time()


@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "Привет!\n"
        "Это развлекательный и модерационный бот бот.\n"
        "Если хочешь узнать более подробную информацию о командах: /help"
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
            version_path = Path(__file__).resolve().parent.parent / "version.json"
            with version_path.open() as f:
                version_data = json.load(f)
                version = version_data.get("version", "unknown")

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
            version = branch = commit = "unknown"
            repo_url = ""

        update_status = "⚠️ Не удалось проверить обновления"
        if all([branch != "unknown", version != "unknown", repo_url]):
            try:
                if "github.com" not in repo_url:
                    raise ValueError("Поддерживаются только GitHub репозитории")

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
                        if resp.status == 200:
                            data = await resp.json()
                            latest_commit = data["commit"]["sha"][:7]
                            if latest_commit != commit:
                                update_status = f"⚡️ <b>Доступно обновление</b>: {branch}@{latest_commit}"
                            else:
                                update_status = "😌 <b>Версия актуальна</b>"
                        else:
                            update_status = f"⚠️ Ошибка API: {resp.status}"
            except Exception as e:
                update_status = f"⚠️ Ошибка проверки: {str(e)}"

        status_message = (
            f"<blockquote><b>🍕 Komaru FunBox</b>\n"
            f"🧬 Версия: <code>{version}</code>\n"
            f"🌿 Ветка: {branch}\n"
            f"{update_status}\n"
            f"⏳ Пинг: {int(ping)} мс\n"
            f"🚀 Аптайм: {uptime_str}\n"
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


@base_router.message(Command("restart"))
async def cmd_restart(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ Эта команда только для персонала.")
        return
    await message.answer("Перезапускаюсь... 🔄")

    try:
        subprocess.Popen(["sudo", "systemctl", "restart", "komaru-funbox.service"])
    except Exception:
        await error_report(message, bot, "restart", traceback.format_exc())


@base_router.message(Command("update"))
async def cmd_restart(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not db.has_permission(user_id, chat_id, 4):
        await message.reply("❌ Эта команда только для персонала.")
        return

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
            if resp.status == 200:
                data = await resp.json()
                latest_commit = data["commit"]["sha"][:7]
                if not latest_commit != commit:
                    return await message.reply("☃️ Версия актуальна")
            else:
                return await message.reply(f"⚠️ Ошибка API: {resp.status}")

    await message.reply("🔄 Обновляюсь...")

    try:
        subprocess.Popen(["sudo", "systemctl", "restart", "komaru-funbox.service"])
    except Exception:
        await error_report(message, bot, "restart", traceback.format_exc())
