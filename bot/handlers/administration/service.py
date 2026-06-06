import asyncio
import os
import subprocess
import traceback
import uuid
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot import CACHE_DIR
from bot.database.database import Database
from bot.database.redis_client import redis_db
from bot.utils.aio_tools import error_report

admin_service_router = Router()


@admin_service_router.message(Command("restart"))
async def cmd_restart(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        if not await db.has_permission(user_id, chat_id, 4):
            await message.reply("❌ Эта команда только для персонала.")
            return
        await message.answer("Перезапускаюсь... 🔄")

        os._exit(1)
    except Exception:
        await error_report(message, bot, "restart", traceback.format_exc())


@admin_service_router.message(Command("update"))
async def cmd_update(message: Message, bot: Bot, db: Database):
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
        repo_url = "https://github.com/Not-a-dude/Komaru-FunBox"
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
        await redis_db.client.delete("check_models_cache")
    except:
        await error_report(message, bot, "update", traceback.format_exc())
        return await update_msg.edit_text(
            "⚠️ Произошла ошибка при удалении кэша рабочих моделей"
        )

    try:
        await update_msg.edit_text("⏳ Получаю изменения из репозитория...")
        git_process = await asyncio.create_subprocess_exec(
            "git",
            "pull",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, git_stderr = await git_process.communicate()

        if git_process.returncode != 0:
            return await update_msg.edit_text(
                f"❌ Ошибка git pull: {git_stderr.decode()}"
            )

        await update_msg.edit_text("🔄 Обновление прошло успешно, перезапускаюсь...")
        os._exit(1)
    except Exception:
        await error_report(message, bot, "update", traceback.format_exc())


@admin_service_router.message(Command("logs"))
async def cmd_send_logs(message: Message, bot: Bot, db: Database):
    source_log = CACHE_DIR / "bot.log"
    out_path = CACHE_DIR / f"send_{uuid.uuid4()}.log"

    try:
        if not await db.has_permission(message.from_user.id, message.chat.id, 4):  # type: ignore
            await message.reply("❌ Эта команда только для персонала.")
            return

        if not source_log.exists():
            await message.reply("❌ Файл логов еще не создан.")
            return

        with open(source_log, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-100:]

        with open(out_path, "w", encoding="utf-8") as temp_f:
            temp_f.writelines(last_lines)

        await message.reply_document(
            FSInputFile(out_path, filename="bot_last_logs.log"),
            caption="📝 Последние 100 строк лога из файла:",
        )

    except Exception:
        await error_report(message, bot, "logs", traceback.format_exc())
    finally:
        if out_path.exists():
            out_path.unlink()
