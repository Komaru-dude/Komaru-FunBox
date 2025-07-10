import traceback
from datetime import datetime

import pytz
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report

time_router = Router()
moscow_tz = pytz.timezone("Europe/Moscow")


@time_router.message(Command("new_year"), CooldownFilter("time", 5))
async def cmd_time_to_new_year(message: Message, bot: Bot):
    try:
        tz = moscow_tz

        event_date = datetime(2026, 1, 1, 0, 0, 0)
        event_date = tz.localize(event_date)

        now = datetime.now(tz)
        time_delta = event_date - now

        if time_delta.days < 0 or (time_delta.days == 0 and time_delta.seconds <= 0):
            await message.reply("🎉 УРА! 2026 год уже наступил!")
            return

        days = time_delta.days
        hours, remainder = divmod(time_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        await message.reply(
            f"⏳ До 2026 года осталось: {days} дней, {hours} часов, {minutes} минут, {seconds} секунд!"
        )
    except Exception:
        await error_report(message, bot, "new_year", traceback.format_exc())


@time_router.message(Command("birthdays"), CooldownFilter("time", 5))
async def cmd_cats_birthdays(message: Message, bot: Bot):
    try:
        tz = moscow_tz

        cats = {
            "Комуги": tz.localize(datetime(2016, 3, 23)),
            "Комару": tz.localize(datetime(2017, 5, 22)),
            "Кокоа": tz.localize(datetime(2019, 5, 12)),
            "Панчан": tz.localize(datetime(2016, 12, 13)),
            "Гома": tz.localize(datetime(2013, 10, 20)),
            "Тобо-кун": tz.localize(datetime(2018, 4, 25)),
            "Суу": tz.localize(datetime(2015, 2, 14)),
            "Горомару": tz.localize(datetime(2015, 11, 10)),
        }

        now = datetime.now(tz)
        responses = []

        for name, birthday in cats.items():
            next_birthday = birthday.replace(year=now.year)

            if next_birthday.date() == now.date():
                responses.append(
                    f"🎉 Сегодня день рождения у {name}! Поздравьте кошку! 🎂"
                )
                continue

            if next_birthday < now:
                next_birthday = next_birthday.replace(year=now.year + 1)

            time_delta = next_birthday - now
            days, remainder = divmod(time_delta.total_seconds(), 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)

            responses.append(
                f"⏳ {name}: через {int(days)} дней, {int(hours)} часов, {int(minutes)} минут, {int(seconds)} секунд "
                f"(день рождения {next_birthday.date()})."
            )

        if responses:
            await message.reply("\n".join(responses))
        else:
            await error_report(message, bot, "birthdays", "📛 Отсутствуют ответы")
    except Exception:
        await error_report(message, bot, "birthdays", traceback.format_exc())


@time_router.message(Command("revx"), CooldownFilter("bradok", 15))
async def cmd_time_to_revx(message: Message, bot: Bot):
    try:
        tz = moscow_tz

        event_date = datetime(2026, 4, 18, 0, 0, 0)
        event_date = tz.localize(event_date)

        now = datetime.now(tz)
        time_delta = event_date - now

        if time_delta.days < 0 or (time_delta.days == 0 and time_delta.seconds <= 0):
            await message.reply("🎉 УРА! Др ревха наступил!")
            return

        days = time_delta.days
        hours, remainder = divmod(time_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        await message.reply(
            f"⏳ До днюхи ревха осталось: {days} дней, {hours} часов, {minutes} минут, {seconds} секунд!"
        )
    except Exception:
        await error_report(message, bot, "birthdays", traceback.format_exc())
