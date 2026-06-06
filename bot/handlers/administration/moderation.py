import traceback

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from bot import API_URL
from bot.database.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report
from bot.utils.bot_tools import fetch_json
from bot.utils.global_storage import eco_config

admin_mods_router = Router()


@admin_mods_router.message(Command("reset_cooldown"))
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


@admin_mods_router.message(Command("bot_ban"))
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


@admin_mods_router.message(Command("bot_unban"))
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


@admin_mods_router.message(Command("delete_user"))
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


@admin_mods_router.message(Command("add_money"), CooldownFilter("money_tools", 15))
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


@admin_mods_router.message(Command("remove_money"), CooldownFilter("money_tools", 15))
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
