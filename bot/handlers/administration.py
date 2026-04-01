import asyncio
import os
import subprocess
import traceback
import uuid
from urllib.parse import urlparse

import aiohttp
from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot import API_URL, CACHE_DIR, DATA_DIR
from bot.database.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report, fetch_json
from bot.utils.global_storage import eco_config

admin_router = Router()
models_path = DATA_DIR / "models.json"


@admin_router.message(Command("restart"))
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


@admin_router.message(Command("update"))
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


@admin_router.message(Command("logs"))
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


@admin_router.message(Command("bot_ban"))
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
                await error_report(message, bot, "bot_ban", traceback.format_exc())
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

    if await db.is_user_botbanned(target_id):
        await message.reply("❌ Пользователь уже заблокирован")
        return

    try:
        await db.bot_ban(target_id)
        await message.reply(f"✅ Пользователь {first_name} был заблокирован")
    except Exception:
        await error_report(message, bot, "bot_ban", traceback.format_exc())


@admin_router.message(Command("bot_unban"))
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
                await error_report(message, bot, "bot_unban", traceback.format_exc())
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

    if not await db.is_user_botbanned(target_id):
        await message.reply("❌ Пользователь уже разблокирован")
        return

    try:
        await db.bot_unban(target_id)
        await message.reply(f"✅ Пользователь {first_name} был разблокирован")
    except Exception:
        await error_report(message, bot, "bot_unban", traceback.format_exc())


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
    except Exception:
        await error_report(message, bot, "ban_media", traceback.format_exc())


@admin_router.message(
    Command("get_active_users_count"), CooldownFilter("get_au_count", 120, True)
)
async def cmd_get_active_users_count(message: Message, bot: Bot, db: Database):

    try:
        user_id = message.from_user.id

        if message.chat.type != "private":
            await message.reply("❌ Эта команда доступна только в ЛС")
            await db.reset_cooldown(user_id, "get_au_count")
            return

        if not await db.has_permission(user_id, message.chat.id, 4):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        ausers_count = await db.get_active_users_count()
        await message.reply(f"👤 Количество активных пользователей: {ausers_count}")
    except Exception:
        await error_report(message, bot, "get_au_count", traceback.format_exc())


@admin_router.message(Command("add_money"), CooldownFilter("money_tools", 15, True))
async def cmd_add_money(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id

        if not await db.has_permission(user_id, message.chat.id, 4):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        target_id = None
        money_to_add = 0
        amount_str = None

        split_text = message.text.split(maxsplit=2)
        command_len = len(split_text)

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if command_len < 2:
                await message.reply("📛 Укажите сумму аргументом.")
                return
            amount_str = split_text[1]

        else:
            if command_len == 2:
                target_id = user_id
                amount_str = split_text[1]

            elif command_len == 3:
                target_arg = split_text[1]
                amount_str = split_text[2]

            else:
                await message.reply(
                    "📛 Неправильный формат команды. Используйте: /add_money <сумма> [цель]."
                )
                return

            if target_id is None:
                if target_arg.startswith("@"):
                    username = target_arg[1:]
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
                        await error_report(
                            message, bot, "add_money_api", traceback.format_exc()
                        )
                        await message.reply("❌ Произошла ошибка при обращении к API.")
                        return

                elif target_arg.isdigit():
                    target_id = int(target_arg)

                else:
                    await message.reply(
                        "📛 Неправильно указана цель (должен быть @юзернейм или ID)."
                    )
                    return

        try:
            money_to_add = float(amount_str)
            if money_to_add <= 0:
                await message.reply("❌ Сумма должна быть положительным числом.")
                return
        except ValueError:
            await message.reply("❌ Сумма должна быть числом.")
            return

        if target_id is None:
            await message.reply("❌ Не удалось определить целевого пользователя.")
            return

        target_bal = await db.get_global_user_param(target_id, "money")
        new_balance = target_bal + money_to_add
        await db.set_global_user_param(target_id, "money", new_balance)

        await message.reply(
            f"✅ Успешно добавлено {money_to_add} {eco_config['currency_sign']} для пользователя {target_id}.\n"
            f"Новый баланс: {new_balance} {eco_config['currency_sign']}"
        )

    except Exception:
        await error_report(message, bot, "add_money", traceback.format_exc())


@admin_router.message(Command("remove_money"), CooldownFilter("money_tools", 15, True))
async def cmd_remove_money(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id

        if not await db.has_permission(user_id, message.chat.id, 4):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        target_id = None
        money_to_remove = 0
        amount_str = None

        split_text = message.text.split(maxsplit=2)
        command_len = len(split_text)

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            if command_len < 2:
                await message.reply("📛 Укажите сумму аргументом.")
                return
            amount_str = split_text[1]

        else:
            if command_len == 2:
                target_id = user_id
                amount_str = split_text[1]

            elif command_len == 3:
                target_arg = split_text[1]
                amount_str = split_text[2]

            else:
                await message.reply(
                    "📛 Неправильный формат команды. Используйте: /remove_money <сумма> [цель]."
                )
                return

            if target_id is None:
                if target_arg.startswith("@"):
                    username = target_arg[1:]
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
                        await error_report(
                            message, bot, "remove_money_api", traceback.format_exc()
                        )
                        await message.reply("❌ Произошла ошибка при обращении к API.")
                        return

                elif target_arg.isdigit():
                    target_id = int(target_arg)

                else:
                    await message.reply(
                        "📛 Неправильно указана цель (должен быть @юзернейм или ID)."
                    )
                    return

        try:
            money_to_remove = float(amount_str)
            if money_to_remove <= 0:
                await message.reply("❌ Сумма должна быть положительным числом.")
                return
        except ValueError:
            await message.reply("❌ Сумма должна быть числом.")
            return

        if target_id is None:
            await message.reply("❌ Не удалось определить целевого пользователя.")
            return

        target_bal = await db.get_global_user_param(target_id, "money")

        new_balance = target_bal - money_to_remove

        await db.set_global_user_param(target_id, "money", new_balance)

        await message.reply(
            f"✅ Успешно вычтено {money_to_remove} {eco_config['currency_sign']} у пользователя {target_id}.\n"
            f"Новый баланс: {new_balance} {eco_config['currency_sign']}"
        )

    except Exception:
        await error_report(message, bot, "remove_money", traceback.format_exc())


@admin_router.message(Command("grant_premium"), CooldownFilter("premium_tools", 15))
async def cmd_grant_premium(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id

        if not await db.has_permission(user_id, message.chat.id, 4):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        target_id = None
        first_name = None

        split_text = message.text.split(maxsplit=1)

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            first_name = message.reply_to_message.from_user.first_name
        else:
            if len(split_text) < 2:
                await message.reply(
                    "❌ Укажите пользователя через реплай, @username или ID.\n"
                    "Пример: <code>/grant_premium @username</code> или <code>/grant_premium 123456789</code>",
                    parse_mode=ParseMode.HTML,
                )
                return

            target_arg = split_text[1]

            if target_arg.startswith("@"):
                username = target_arg[1:]
                try:
                    data = await fetch_json(f"{API_URL}/user/{username}")
                    if "user_id" in data:
                        target_id = int(data["user_id"])
                    else:
                        await message.reply(
                            f"❌ Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                        )
                        return
                except Exception:
                    await error_report(
                        message, bot, "grant_premium", traceback.format_exc()
                    )
                    return
            elif target_arg.isdigit():
                target_id = int(target_arg)
            else:
                await message.reply(
                    "❌ Неправильно указана цель (должен быть @юзернейм или ID)."
                )
                return

            try:
                data = await fetch_json(
                    f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                )
                first_name = data.get("first_name", "Неизвестный")
            except Exception:
                first_name = "Неизвестный"

        current_tier = await db.get_user_tier(target_id)
        if current_tier > 0:
            await message.reply(
                f"⚠️ Пользователь {first_name} уже имеет премиум статус."
            )
            return

        await db.set_user_tier(target_id, 1)
        await message.reply(
            f"✅ Пользователю {first_name} ({target_id}) выдан премиум статус.",
        )

    except Exception:
        await error_report(message, bot, "grant_premium", traceback.format_exc())


@admin_router.message(Command("revoke_premium"), CooldownFilter("premium_tools", 15))
async def cmd_revoke_premium(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id

        if not await db.has_permission(user_id, message.chat.id, 4):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        target_id = None
        first_name = None

        split_text = message.text.split(maxsplit=1)

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            first_name = message.reply_to_message.from_user.first_name
        else:
            if len(split_text) < 2:
                await message.reply(
                    "❌ Укажите пользователя через реплай, @username или ID.\n"
                    "Пример: <code>/revoke_premium @username</code> или <code>/revoke_premium 123456789</code>",
                    parse_mode=ParseMode.HTML,
                )
                return

            target_arg = split_text[1]

            if target_arg.startswith("@"):
                username = target_arg[1:]
                try:
                    data = await fetch_json(f"{API_URL}/user/{username}")
                    if "user_id" in data:
                        target_id = int(data["user_id"])
                    else:
                        await message.reply(
                            f"❌ Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                        )
                        return
                except Exception:
                    await error_report(
                        message, bot, "revoke_premium", traceback.format_exc()
                    )
                    return
            elif target_arg.isdigit():
                target_id = int(target_arg)
            else:
                await message.reply(
                    "❌ Неправильно указана цель (должен быть @юзернейм или ID)."
                )
                return

            try:
                data = await fetch_json(
                    f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                )
                first_name = data.get("first_name", "Неизвестный")
            except Exception:
                first_name = "Неизвестный"

        current_tier = await db.get_user_tier(target_id)
        if current_tier == 0:
            await message.reply(
                f"⚠️ Пользователь {first_name} не имеет премиум статуса."
            )
            return

        await db.set_user_tier(target_id, 0)
        await message.reply(
            f"✅ Премиум статус отозван у пользователя {first_name} ({target_id}).",
        )

    except Exception:
        await error_report(message, bot, "revoke_premium", traceback.format_exc())
