import os
import time
import psutil
import asyncio
import aiohttp
import json
import subprocess
import traceback
import uuid
import base64
from pathlib import Path
from urllib.parse import urlparse
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from bot import database
from bot.utils.aio_tools import error_report, fetch_json
from bot.utils.global_storage import CACHE_DIR

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
        ping = int((end_time - ping_start_time) * 1000)

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
                data = json.load(f)
                local_version = data.get("version", "unknown")
        except Exception:
            local_version = "unknown"

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
        except Exception:
            branch = "unknown"
            commit = "unknown"

        repo_url = "https://github.com/Komaru-dude/Komaru-FunBox"

        update_status = "⚠️ Не удалось проверить обновления"
        latest_version = None
        latest_commit = None

        if branch != "unknown" and commit != "unknown" and repo_url:
            try:
                async with aiohttp.ClientSession() as session:
                    version_json_url = (
                        "https://api.github.com/repos/Komaru-dude/Komaru-FunBox/"
                        "contents/bot/version.json"
                    )
                    async with session.get(
                        version_json_url, headers={"User-Agent": "KomaruBot/1.0"}
                    ) as resp_v:
                        if resp_v.status != 200:
                            raise Exception(
                                f"Не удалось получить version.json (status {resp_v.status})"
                            )
                        vi_data = await resp_v.json()
                    content_base64 = vi_data.get("content")
                    if not content_base64:
                        raise Exception("Нет содержимого version.json")
                    content_bytes = base64.b64decode(content_base64)
                    version_list = json.loads(content_bytes.decode("utf-8"))

                    branch_entry = next(
                        (item for item in version_list if item["branch"] == branch),
                        None,
                    )
                    if branch_entry:
                        latest_version = branch_entry.get("version")
                    else:
                        raise Exception("Не найдена версия для ветки " + branch)

                    branch_api_url = f"https://api.github.com/repos/Komaru-dude/Komaru-FunBox/branches/{branch}"
                    async with session.get(
                        branch_api_url, headers={"User-Agent": "KomaruBot/1.0"}
                    ) as resp_b:
                        if resp_b.status != 200:
                            raise Exception(
                                f"Не удалось получить данные ветки (status {resp_b.status})"
                            )
                        branch_data = await resp_b.json()
                    latest_commit = branch_data["commit"]["sha"][:7]

                if latest_commit != commit:
                    update_status = f"⚡️ <b>Доступно обновление</b>: {latest_version}@{latest_commit}"
                else:
                    if latest_version != local_version:
                        update_status = f"⚡️ <b>Доступно обновление</b>: {latest_version}@{latest_commit}"
                    else:
                        update_status = (
                            f"😌 <b>Версия актуальна</b>: {local_version}@{commit}"
                        )

            except Exception as e:
                update_status = f"⚠️ Ошибка проверки: {str(e)}"

        status_message = (
            f"<blockquote><b>🍕 Komaru FunBox</b>\n"
            f"🧬 Версия: <code>{local_version}@{commit}</code>\n"
            f"🌿 Ветка: <b>{branch}</b>\n"
            f"{update_status}\n"
            f"⏳ Пинг: {ping} мс\n"
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
    if not await db.has_permission(user_id, chat_id, 4):
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
                if not latest_commit != commit:
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
        subprocess.Popen(["sudo", "systemctl", "restart", "komaru-funbox.service"])
    except Exception:
        await error_report(message, bot, "restart", traceback.format_exc())


@base_router.message(Command("logs"))
async def cmd_send_logs(message: Message, bot: Bot):
    try:
        out_path = CACHE_DIR / random_log_name

        if not await db.has_permission(message.from_user.id, message.chat.id, 4):
            await message.reply("❌ Эта команда только для персонала.")
            return

        random_log_name = f"{uuid.uuid4()}.log"

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

        if len(split_text) < 4:
            await message.reply(
                "❌ Некорректный синтаксис!\nИспользуйте: <code>/reset_cooldown chat_id user_id command_name</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            target_chat_id = int(split_text[1])
            target_user_id = int(split_text[2])
        except ValueError:
            await message.reply("❌ chat_id и user_id должны быть числами.")
            return
        target_command = split_text[3]

        await db.reset_cooldown(target_user_id, target_chat_id, target_command)
        await message.reply("✅ Успешно сброшено")
    except Exception:
        await error_report(message, bot, "reset_cooldown", traceback.format_exc())
