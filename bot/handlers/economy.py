import os
import random
import traceback
from aiogram import Router, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from bot.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.filters.chat_type import ChatTypeFilter
from bot.utils.aio_tools import error_report, get_user_id

eco_router = Router()


@eco_router.message(
    Command("work"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    CooldownFilter(command="work", cooldown=14400),
)
async def cmd_work(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        eco_data = await db.get_eco_settings()
        current_bal = await db.get_global_user_param(user_id, "money")

        min_income = eco_data["min_work_income"]
        max_income = eco_data["max_work_income"]
        current_income = random.randint(min_income, max_income)

        new_bal = current_bal + current_income
        await db.set_global_user_param(user_id, "money", new_bal)
        await message.reply(
            f"👨‍💻 Вы заработали: {current_income}\n{eco_data["currency_sign"]} Ваш новый баланс: {new_bal}"
        )
    except Exception:
        await db.reset_cooldown(user_id, "work")
        await error_report(message, bot, "work", traceback.format_exc())


@eco_router.message(
    Command("steal"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    CooldownFilter(command="steal", cooldown=14400),
)
async def cmd_steal(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        eco_data = await db.get_eco_settings()
        current_bal = await db.get_global_user_param(user_id, "money")
        if current_bal < eco_data["max_steal_penalty"] / 2:
            await message.reply(
                f"❌ Вам нужно иметь на балансе хотя бы половину от максимальной суммы штрафа ({eco_data["currency_sign"]}{eco_data['max_steal_penalty'] / 2})"
            )
            await db.reset_cooldown(user_id, "steal")
            return

        min_income = eco_data["min_steal_income"]
        max_income = eco_data["max_steal_income"]
        current_income = random.randint(min_income, max_income)

        min_penalty = eco_data["min_steal_penalty"]
        max_penalty = eco_data["max_steal_penalty"]
        current_penalty = random.randint(min_penalty, max_penalty)

        fail_percent = eco_data["steal_fail_percent"]
        if random.randint(1, 100) <= fail_percent:
            new_bal = current_bal - current_penalty
            await message.reply(
                f"😔 Вам не повезло.\n🧨 Вы потеряли: {current_penalty}\n{eco_data["currency_sign"]} Ваш новый баланс: {new_bal}"
            )
        else:
            new_bal = current_bal + current_income
            await message.reply(
                f"🤑 Повезло!\n💡 Вы заработали: {current_income}\n{eco_data["currency_sign"]} Ваш новый баланс: {new_bal}"
            )

        await db.set_global_user_param(user_id, "money", new_bal)

    except Exception:
        await db.reset_cooldown(user_id, "steal")
        await error_report(message, bot, "steal", traceback.format_exc())


@eco_router.message(
    Command("rob"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    CooldownFilter(command="rob", cooldown=28800),
)
async def cmd_rob(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        split_text = message.text.split()
        eco_data = await db.get_eco_settings()
        target_id, get_id_error = await get_user_id(message)

        if len(split_text) < 2 and not message.reply_to_message:
            await message.reply(
                "❌ Требуется упоминание/ответ на сообщение пользователя."
            )
            await db.reset_cooldown(user_id, "rob")
            return

        if get_id_error:
            await message.reply("❌ Не удалось получить user_id!")
            await db.reset_cooldown(user_id, "rob")
            return

        user_bal = await db.get_global_user_param(user_id, "money")
        target_user_bal = await db.get_global_user_param(target_id, "money")

        if target_user_bal < 0:
            await message.reply("❌ У цели нет наличных")
            await db.reset_cooldown(user_id, "rob")
            return

        succeed_percent = random.randint(
            eco_data["rob_min_percent"], eco_data["rob_max_percent"]
        )
        if target_user_bal * succeed_percent / 100 < 1:
            await message.reply("❌ У цели недостаточно наличных")
            await db.reset_cooldown(user_id, "rob")
            return

        fail_percent = eco_data["rob_fail_percent"]
        if random.randint(1, 100) <= fail_percent:
            new_bal = user_bal / 2
            await message.reply(f"😔 Вам не повезло.\n🧨 Ваш новый баланс: {new_bal}")
        else:
            target_penalty = target_user_bal * (succeed_percent / 100)
            target_new_bal = target_user_bal - target_penalty
            new_bal = user_bal + target_penalty
            await message.reply(
                f"🤑 Повезло!\n💡 Вы украли: {target_penalty}\n{eco_data["currency_sign"]}\nНовый баланс цели {target_new_bal}\nВаш новый баланс: {new_bal}"
            )

        await db.set_global_user_param(user_id, "money", new_bal)
        await db.set_global_user_param(target_id, "money", target_new_bal)

    except ZeroDivisionError:
        profile_link = f"tg://user?id={os.getenv('OWNER_ID')}"
        await message.reply(
            f'❌ Произошло деление на ноль! Обратитесь к владельцу: <a href="{profile_link}">Тык</a>',
            parse_mode=ParseMode.HTML,
        )  # Не используем юзернейм во избежании его изменения
    except Exception:
        await db.reset_cooldown(user_id, "rob")
        await error_report(message, bot, "rob", traceback.format_exc())
