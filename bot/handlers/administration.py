import asyncio
import os
import platform
import shutil
import subprocess
import traceback
import uuid
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot import API_URL, CACHE_DIR, DATA_DIR
from bot.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report, fetch_json

admin_router = Router()
models_path = DATA_DIR / "models.json"


def get_service_name() -> str:
    folder_name = Path(__file__).parent.parent.parent.name
    if "test" in folder_name:
        return "komaru-funbox_test.service"
    else:
        return "komaru-funbox.service"


SERVICE_NAME = get_service_name()


@admin_router.message(Command("restart"))
async def cmd_restart(message: Message, bot: Bot, db: Database):
    if platform.system() != "Linux" or not shutil.which("systemctl"):
        await message.reply(
            "❌ Платформа не поддерживается\n📀 Требуется Linux + Systemd"
        )
        return
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


@admin_router.message(Command("update"))
async def cmd_update(message: Message, bot: Bot, db: Database):
    if platform.system() != "Linux" or not shutil.which("systemctl"):
        await message.reply(
            "❌ Платформа не поддерживается\n📀 Требуется Linux + Systemd"
        )
        return
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


@admin_router.message(Command("logs"))
async def cmd_send_logs(message: Message, bot: Bot, db: Database):
    try:
        if platform.system() != "Linux" or not shutil.which("systemctl"):
            await message.reply(
                "❌ Платформа не поддерживается\n📀 Требуется Linux + Systemd"
            )
            return
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


@admin_router.message(Command("reset_cooldown"))
async def cmd_reset_cooldown(message: Message, bot: Bot, db: Database):
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


@admin_router.message(Command("ban_media"))
async def cmd_ban_user(message: Message, bot: Bot, db: Database):
    user_id = message.from_user.id
    chat_id = message.chat.id
    target_id = None
    first_name = None

    if message.chat.type in ["private", "channel"]:
        await message.reply("❌ Эта команда доступна только в группах/супергруппах")
        return

    if not await db.has_permission(user_id, chat_id, 4):
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
                data = await fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = int(data["user_id"])
                else:
                    await message.reply(
                        f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                    )
                    return

            except Exception:
                await error_report(message, bot, "ban_media", traceback.format_exc())
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = int(split_text[1])
        else:
            await message.reply(
                "Укажите пользователя через реплай, @username или айди."
            )
            return

        try:
            data = await fetch_json(
                f"{API_URL}/first_name/{message.chat.id}/{target_id}"
            )
            first_name = data.get("first_name", "Неизвестный")
        except Exception:
            first_name = "Неизвестный"

    if await db.is_user_mediabanned(target_id):
        await message.reply("❌ Пользователь уже заблокирован")
        return

    try:
        await db.mediaban_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был заблокирован")
    except Exception as e:
        await error_report(message, bot, "ban_media", traceback.format_exc())


@admin_router.message(Command("unban_media"))
async def cmd_unban_user(message: Message, bot: Bot, db: Database):
    user_id = message.from_user.id
    chat_id = message.chat.id
    target_id = None
    first_name = None

    if message.chat.type in ["private", "channel"]:
        await message.reply("❌ Эта команда доступна только в группах/супергруппах")
        return

    if not await db.has_permission(user_id, chat_id, 4):
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
                data = await fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = int(data["user_id"])
                else:
                    await message.reply(
                        f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                    )
                    return

            except Exception:
                await error_report(message, bot, "unban_media", traceback.format_exc())
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = int(split_text[1])
        else:
            await message.reply(
                "Укажите пользователя через реплай, @username или айди."
            )
            return

        try:
            data = await fetch_json(
                f"{API_URL}/first_name/{message.chat.id}/{target_id}"
            )
            first_name = data.get("first_name", "Неизвестный")
        except Exception:
            first_name = "Неизвестный"

    if not await db.is_user_mediabanned(target_id):
        await message.reply("❌ Пользователь уже разблокирован")
        return

    try:
        await db.mediaunban_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был разблокирован")
    except Exception as e:
        await error_report(message, bot, "unban_media", traceback.format_exc())


@admin_router.message(Command("delete_user"))
async def cmd_wipe_user(message: Message, bot: Bot, db: Database):
    user_id = message.from_user.id
    chat_id = message.chat.id
    target_id = None
    first_name = None

    if message.chat.type in ["private", "channel"]:
        await message.reply("❌ Эта команда доступна только в группах/супергруппах")
        return

    if not await db.has_permission(user_id, chat_id, 4):
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
                data = await fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = int(data["user_id"])
                else:
                    await message.reply(
                        f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                    )
                    return

            except Exception:
                await error_report(message, bot, "ban_media", traceback.format_exc())
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = int(split_text[1])
        else:
            await message.reply(
                "Укажите пользователя через реплай, @username или айди."
            )
            return

        try:
            data = await fetch_json(
                f"{API_URL}/first_name/{message.chat.id}/{target_id}"
            )
            first_name = data.get("first_name", "Неизвестный")
        except Exception:
            first_name = "Неизвестный"

    try:
        await db.delete_global_user(target_id)
        await message.reply(f"✅ Пользователь {first_name} был удалён")
    except Exception as e:
        await error_report(message, bot, "ban_media", traceback.format_exc())

@admin_router.message(Command("get_active_users_count"), CooldownFilter("get_au_count", 120, True))
async def cmd_get_active_users_count(message: Message, db: Database):

    if message.chat.type != "private":
        await message.reply("❌ Эта команда доступна только в ЛС")
        return

    if not await db.has_permission(message.from_user.id, message.chat.id, 4):
        await message.reply("❌ У вас недостаточно прав для выполнения этой команды.")
        return
    
    ausers_count = await db.get_active_users_count()
    await message.reply(f"👤 Количество активных пользователей: {ausers_count}")
