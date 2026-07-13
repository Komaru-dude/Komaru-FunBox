import time
import traceback
from datetime import datetime

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from bot import API_URL, logger
from bot.database.database import Database
from bot.database.logic import premium as premium_logic
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report
from bot.utils.bot_tools import fetch_json

admin_premium_router = Router()


@admin_premium_router.message(
    Command("grant_premium"), CooldownFilter("premium_tools", 7)
)
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
        days = None

        split_text = message.text.split()

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            first_name = message.reply_to_message.from_user.first_name
            if len(split_text) >= 2:
                try:
                    days = int(split_text[1])
                except ValueError:
                    await message.reply("❌ Количество дней должно быть числом.")
                    return
        else:
            if len(split_text) < 2:
                await message.reply(
                    "❌ Укажите пользователя через реплай, @username или ID.\n"
                    "Пример: <code>/grant_premium @username</code> или <code>/grant_premium 123456789 30</code> где 30 - количество дней премиума",
                    parse_mode=ParseMode.HTML,
                )
                return

            target_arg = split_text[1]
            if len(split_text) >= 3:
                try:
                    days = int(split_text[2])
                except ValueError:
                    await message.reply("❌ Количество дней должно быть числом.")
                    return

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

        if target_id is None:
            await message.reply("❌ Не удалось определить целевого пользователя.")
            return

        expire = await db.get_premium_expire(target_id)
        now = int(time.time())

        if days is None:
            if expire and expire > now:
                await message.reply(
                    f"⚠️ Пользователь {first_name} уже имеет премиум статус."
                )
                return

            await db.set_user_tier(target_id, 1)
            await message.reply(
                f"✅ Пользователю {first_name} ({target_id}) выдан премиум статус.",
            )
            return

        new_expire = await db.add_premium_days(target_id, days)

        dt_str = datetime.fromtimestamp(new_expire).strftime("%Y-%m-%d %H:%M:%S")
        await message.reply(
            f"✅ Пользователю {first_name} ({target_id}) выдано {days} дней премиума. Срок до: {dt_str}.",
        )

    except Exception:
        await error_report(message, bot, "grant_premium", traceback.format_exc())


@admin_premium_router.message(
    Command("revoke_premium"), CooldownFilter("premium_tools", 7)
)
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
        days = None

        split_text = message.text.split()

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            first_name = message.reply_to_message.from_user.first_name
            if len(split_text) >= 2:
                try:
                    days = int(split_text[1])
                except ValueError:
                    await message.reply("❌ Количество дней должно быть числом.")
                    return
        else:
            if len(split_text) < 2:
                await message.reply(
                    "❌ Укажите пользователя через реплай, @username или ID.\n"
                    "Пример: <code>/revoke_premium @username</code> или <code>/revoke_premium 123456789 5</code>",
                    parse_mode=ParseMode.HTML,
                )
                return

            target_arg = split_text[1]
            if len(split_text) >= 3:
                try:
                    days = int(split_text[2])
                except ValueError:
                    await message.reply("❌ Количество дней должно быть числом.")
                    return

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

        if target_id is None:
            await message.reply("❌ Не удалось определить целевого пользователя.")
            return

        expire = await db.get_premium_expire(target_id)
        now = int(time.time())

        if days is None:
            if not expire or expire <= now:
                await message.reply(
                    f"⚠️ Пользователь {first_name} не имеет премиум статуса."
                )
                return

            await db.set_user_tier(target_id, 0)
            await message.reply(
                f"✅ Премиум статус отозван у пользователя {first_name} ({target_id}).",
            )
            return

        new_expire = await db.remove_premium_days(target_id, days)

        if new_expire == 0:
            await message.reply(
                f"✅ Премиум статус отозван у пользователя {first_name} ({target_id})."
            )
            return

        remaining_seconds = new_expire - now
        remaining_days = remaining_seconds // (24 * 60 * 60)
        dt_str = datetime.fromtimestamp(new_expire).strftime("%Y-%m-%d %H:%M:%S")
        await message.reply(
            f"✅ Срок премиума у пользователя {first_name} ({target_id}) уменьшён на {days} дней. Оставшийся срок: {remaining_days} дней (до {dt_str})."
        )

    except Exception:
        await error_report(message, bot, "revoke_premium", traceback.format_exc())


@admin_premium_router.message(
    Command("premium_stats"), CooldownFilter("premium_tools", 5)
)
async def cmd_premium_stats(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id

        if not await db.has_permission(user_id, message.chat.id, 4):
            await message.reply(
                "❌ У вас недостаточно прав для выполнения этой команды."
            )
            return

        pool = await db.ensure_connection()
        stats = await premium_logic.get_premium_stats(pool)
        top = await premium_logic.get_top_premium_buyers(pool, 5)

        # Баланс звёзд бота (Telegram Bot API)
        star_balance_line = "⭐ Баланс бота: <i>недоступен</i>"
        try:
            balance = await bot.get_my_star_balance()
            star_balance_line = f"⭐ Баланс бота: <b>{balance.amount}</b>"
        except Exception as e:
            logger.error(f"get_my_star_balance failed: {e}")

        last = stats.get("last_purchase")
        if last:
            last_dt = last["created_at"].strftime("%Y-%m-%d %H:%M")
            last_line = (
                f"🕒 Последняя покупка: <code>{last['user_id']}</code>, "
                f"{last['days']} дн., {last['stars']} ⭐ ({last_dt})"
            )
        else:
            last_line = "🕒 Последняя покупка: <i>ещё не было</i>"

        top_lines = []
        for i, row in enumerate(top, start=1):
            top_lines.append(
                f"{i}. <code>{row['user_id']}</code> — "
                f"{row['purchases']} покуп., {row['stars']} ⭐, {row['days']} дн."
            )
        top_block = "\n".join(top_lines) if top_lines else "<i>пусто</i>"

        text = (
            "📊 <b>Статистика премиума</b>\n\n"
            f"👑 Активных премиумов: <b>{stats['active_premiums']}</b>\n"
            f"🛒 Всего покупок: <b>{stats['total_purchases']}</b> "
            f"(уникальных: <b>{stats['unique_buyers']}</b>)\n"
            f"⭐ Получено звёзд всего: <b>{stats['total_stars']}</b>\n"
            f"📅 Продано дней всего: <b>{stats['total_days_sold']}</b>\n\n"
            f"📈 За 7 дней: <b>{stats['purchases_7d']}</b> покуп. / "
            f"<b>{stats['stars_7d']}</b> ⭐\n"
            f"📈 За 30 дней: <b>{stats['purchases_30d']}</b> покуп. / "
            f"<b>{stats['stars_30d']}</b> ⭐\n\n"
            f"{star_balance_line}\n\n"
            f"{last_line}\n\n"
            f"🏆 <b>Топ покупателей:</b>\n{top_block}"
        )

        await message.reply(text, parse_mode=ParseMode.HTML)

    except Exception:
        await error_report(message, bot, "premium_stats", traceback.format_exc())
