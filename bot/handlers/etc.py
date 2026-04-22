import json
import os
import random
import time
import traceback
from datetime import datetime
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
    URLInputFile,
)
from aiohttp import ClientSession

from bot import API_URL, BASE_DIR, FREE_GAMES_PATH, logger
from bot.database.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.keyboards.callback_data import WeatherCallback
from bot.keyboards.weather_keyboard import create_days_keyboard
from bot.utils.aio_tools import error_report, fetch_json
from bot.utils.global_storage import eco_config

etc_router = Router()


def load_http_codes(filename):
    path = Path(__file__).parent.parent / "media" / filename
    with open(path, "r") as f:
        return json.load(f)


cat_http_codes = load_http_codes("cat_http_codes.json")
WEATHER_CACHE = {}  # Хранит прогнозы на текущий день
BONUM_STICKERS_ID = {
    1: "CAACAgIAAyEFAASbCRfOAAJW2mjT7S6mjNl2eq1K3OsShmsV2K8AAzotAAIEtJhLnn7lET7JhBM2BA",  # Обычный
    2: "CAACAgIAAxkBAAEHtwZpURF3TSiBenasXJH0NQayehM9LQACJZcAAgyRgEqz4u63TP-QeTYE",  # Неудачный
    3: "CAACAgIAAxkBAAEHtw9pURGnLf6gkyGFXIarSX0tqGiE2QACqnwAAnK2iEqzLJoLqlTpTTYE",  # Редкий
    4: "CAACAgIAAxkBAAEHtxBpURGsMmRzKX2wbb_TQpOUK2t47AACzI0AAvkFiUoEM91HhGYvnzYE",  # Очень редкий
}

with open(BASE_DIR / "media" / "weather_codes.json", "r") as f:
    WEATHER_ICONS = {int(k): v for k, v in json.load(f).items()}


@etc_router.message(Command("coffee"), CooldownFilter("418_cat", 604800, silent=True))
async def cmd_tea(message: Message, db: Database, bot: Bot):
    try:
        await db.log_command(message.from_user.id if message.from_user else 0, "coffee")

        t418 = URLInputFile(url="https://http.cat/418.jpg", filename="418.jpg")
        if message.reply_to_message:
            await message.reply_to_message.reply_photo(
                t418,
                caption="418 I'm a <a href='https://ru.wikipedia.org/wiki/HTCPCP'>teapot</a> ☕",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_photo(
                t418,
                caption="418 I'm a <a href='https://ru.wikipedia.org/wiki/HTCPCP'>teapot</a> ☕",
                parse_mode=ParseMode.HTML,
            )
    except TelegramNetworkError:
        await message.reply(
            "📛 Проблемы с интернетом!\n🤔 Не пишите разработчикам об этом, они и так в курсе"
        )
    except Exception:
        await error_report(message, bot, "coffee", traceback.format_exc())


@etc_router.message(Command("http_cat"), CooldownFilter("http_pets", 5))
async def cmd_http_cat(message: Message, bot: Bot):
    try:
        assert message.text
        split_text = message.text.split()
        code = None

        if len(split_text) > 1:
            try:
                user_code = int(split_text[1])
                code = 405 if user_code == 418 else user_code
                if code not in cat_http_codes:
                    code = None
            except ValueError:
                pass

        code = code or random.choice(cat_http_codes)
        url = f"https://http.cat/{code}.jpg"

        try:
            await message.reply_photo(url, caption=f"Ваш HTTP кот: {code}")
        except TelegramBadRequest as e:
            await message.reply(f"📛 Не удалось отправить кота: {e.message}")

    except TelegramNetworkError:
        await message.reply(
            "📛 Проблемы с интернетом!\n🤔 Не пишите разработчикам об этом, они и так в курсе"
        )
    except Exception as e:
        await error_report(message, bot, "http_cat", traceback.format_exc())


@etc_router.message(Command("cat"), CooldownFilter("pets", 15))
async def cmd_cat(message: Message, bot: Bot):
    try:
        await message.reply_photo(
            URLInputFile("https://cataas.com/cat"), caption="🐈‍⬛ Ваш кот:"
        )
    except TelegramNetworkError:
        await message.reply(
            "📛 Проблемы с интернетом!\n🤔 Не пишите разработчикам об этом, они и так в курсе"
        )
    except Exception:
        await error_report(message, bot, "cat", traceback.format_exc())


@etc_router.message(Command("cat_gif"), CooldownFilter("pets", 15))
async def cmd_cat_gif(message: Message, bot: Bot):
    try:
        await message.reply_video(URLInputFile("https://cataas.com/cat/gif"))
    except TelegramNetworkError:
        await message.reply(
            "📛 Проблемы с интернетом!\n🤔 Не пишите разработчикам об этом, они и так в курсе"
        )
    except Exception:
        await error_report(message, bot, "cat_gif", traceback.format_exc())


async def fetch_weather(city: str, day_delta: int):
    if not (0 <= day_delta <= 2):
        return None, "out of range"

    cache_key = f"{city}_{datetime.now().date()}"

    # Попытка получить данные из кэша
    if cache_key in WEATHER_CACHE:
        data = WEATHER_CACHE[cache_key]
        logger.debug("♻️ Используем данные погоды из кэша")
    else:
        url = f"https://api.weatherapi.com/v1/forecast.json?key={os.getenv('WEATHER_API_KEY')}&q={city}&days=7&aqi=yes&alerts=no"
        async with ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None, resp.status
                data = await resp.json()
        WEATHER_CACHE[cache_key] = data
        print("Fetching new data and caching")

    forecast_days = data.get("forecast", {}).get("forecastday", [])
    if day_delta >= len(forecast_days):
        return None, None

    day_data = forecast_days[day_delta]
    query_date = day_data["date"]
    loc = data["location"]

    day_data = day_data["day"]
    cond = day_data["condition"]
    code = cond.get("code", 1000)
    emoji = WEATHER_ICONS.get(code, "❔")

    text = (
        f"<b>{emoji} Погода в {loc['name']}, {loc['country']} на {query_date}</b>\n"
        f"<b>🌡 Средняя температура:</b> {day_data.get('avgtemp_c', 'н/д')}°C\n"
        f"<b>💧 Влажность:</b> {day_data.get('avghumidity', 'н/д')}%\n"
        f"<b>💨 Ветер:</b> {day_data.get('maxwind_kph', 'н/д')} км/ч\n"
        f"<b>👀 Видимость:</b> {day_data.get('avgvis_km', 'н/д')} км\n"
        f"<b>🧪 Давление:</b> {day_data.get('pressure_mb', 'н/д')} мбар\n"
        f"<b>🌞 UV-индекс:</b> {day_data.get('uv', 'н/д')}\n"
        f"<b>💨 Качество воздуха (PM2.5):</b> {day_data.get('air_quality', {}).get('pm2_5', 'н/д')}\n"
    )
    return text, None


@etc_router.message(Command("weather"), CooldownFilter("weather", 150))
async def weather_command(message: Message, bot: Bot, db: Database):
    try:
        if not message.from_user or not message.text:
            return
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await message.reply(
                "❌ Укажите город.\nПример: <code>/weather Москва</code>",
                parse_mode=ParseMode.HTML,
            )
            await db.reset_cooldown(message.from_user.id, "weather")
            return
        city = parts[1]

        text, err = await fetch_weather(city, 0)
        if err or not text:
            await message.reply(f"📛 Ошибка: {err}")
            await db.reset_cooldown(message.from_user.id, "weather")
            return

        keyboard = create_days_keyboard(0, message.from_user.id)
        await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception:
        await error_report(message, bot, "weather", traceback.format_exc())


@etc_router.callback_query(WeatherCallback.filter())
async def weather_callback(
    query: CallbackQuery, callback_data: WeatherCallback, bot: Bot
):
    try:
        try:
            day_delta = callback_data.day
        except (ValueError, IndexError):
            await query.answer("❌ Некорректный запрос", show_alert=True)
            return

        if callback_data.user_id != query.from_user.id:
            await query.answer(
                "❌ Комару не разрешает отвечать на чужие колбэки", show_alert=True
            )
            return

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        try:
            city_line = query.message.text.split("\n")[0]
            city = city_line.split("в ")[1].split(",")[0].strip()
        except (IndexError, AttributeError):
            await query.answer(
                "📛 Не удалось определить город из предыдущего сообщения, обратитесь к разработчику",
                show_alert=True,
            )
            return

        text, err = await fetch_weather(city, day_delta)
        if err or not text:
            await query.answer("📛 Не удалось получить данные", show_alert=True)
            return

        keyboard = create_days_keyboard(day_delta, query.from_user.id)
        await query.message.edit_text(
            text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
        await query.answer()
    except Exception:
        assert isinstance(query.message, Message)
        await error_report(
            query.message, bot, "weather_callback", traceback.format_exc()
        )


@etc_router.message(Command("nillerxs"), CooldownFilter("bradok", 15))
async def cmd_nillerxs(message: Message):
    await message.reply("нильрекс")


@etc_router.message(Command("bonum"))
async def cmd_bonum(message: Message, db: Database, bot: Bot):
    user_id = message.from_user.id if message.from_user else 0
    if not user_id:
        return

    cooldown = eco_config.get("bonum_cooldown", 7200)
    if not await db.is_command_available(user_id, "bonum", cooldown):
        rem = await db.get_cooldown_remaining(user_id, "bonum")
        return await message.reply(
            f"⏳ Попробуй через {rem // 3600}ч {(rem % 3600) // 60}м."
        )

    now = int(time.time())
    raw_ts = await db.get_global_user_param(user_id, "bonum_ts")
    last_use = int(raw_ts) if isinstance(raw_ts, (int, str, float)) else 0

    time_mult = 1.0
    if last_use > 0:
        idle_time = now - (last_use + cooldown)
        if idle_time > 0:
            time_mult += (idle_time // 21600) * 0.1
            time_mult = min(time_mult, 2.5)

    choice = random.choices([1, 2, 3, 4], weights=[1, 14, 55, 30], k=1)[0]
    bonus_amount = 0
    cur = eco_config.get("currency_sign", "🪙")
    sticker_id = BONUM_STICKERS_ID.get(1)

    if choice == 1:
        base = random.randint(*eco_config["bonum_4_rewards"])
        bonus_amount = int(base * time_mult)
        sticker_id = BONUM_STICKERS_ID.get(4)
        msg = f"🏆 <b>Невероятно повезло!</b>\n\n🍀 Редкий бонум!\n💰 Награда: {bonus_amount} {cur}"
    elif choice == 2:
        base = random.randint(*eco_config["bonum_3_rewards"])
        bonus_amount = int(base * time_mult)
        sticker_id = BONUM_STICKERS_ID.get(3)
        msg = f"🌟 <b>Удача!</b>\n\nВы получили солидный бонус: {bonus_amount} {cur}"
    elif choice == 3:
        base = random.randint(*eco_config["bonum_2_rewards"])
        bonus_amount = int(base * time_mult)
        sticker_id = BONUM_STICKERS_ID.get(2)
        msg = f"✨ <b>Бонус:</b>\n\nВы получили {bonus_amount} {cur}"
    else:
        penalty = random.randint(*eco_config["bonum_1_fines"])
        bonus_amount = -penalty
        sticker_id = BONUM_STICKERS_ID.get(1)
        msg = f"💀 <b>Неудача...</b>\n\nВы потеряли: {penalty} {cur}"

    if time_mult > 1.0 and choice != 4:
        msg += f"\n<i>⏱ Бонус ожидания: x{time_mult:.1f}</i>"

    raw_money = await db.get_global_user_param(user_id, "money")
    user_bal = int(raw_money) if isinstance(raw_money, (int, str, float)) else 0

    await db.set_global_user_param(user_id, "money", user_bal + bonus_amount)
    await db.set_global_user_param(user_id, "bonum_ts", now)
    await db.log_command(user_id, "bonum")

    await bot.send_sticker(
        message.chat.id,
        sticker_id
        or "CAACAgIAAyEFAASbCRfOAAJW2mjT7S6mjNl2eq1K3OsShmsV2K8AAzotAAIEtJhLnn7lET7JhBM2BA",
        reply_to_message_id=message.message_id,
    )
    await message.answer(msg, parse_mode="HTML")


@etc_router.message(
    Command("tagall"),
    CooldownFilter("tagall", 900),
    ChatTypeFilter(["group", "supergroup"]),
)
async def cmd_tagall(message: Message, bot: Bot, db: Database):
    try:
        assert message.from_user
        chat_id = message.chat.id
        user_id = message.from_user.id

        if not await db.is_setting_enabled(
            chat_id, "tag"
        ) and not await db.has_permission(user_id, chat_id, 1):
            await message.reply(
                "❌ Функция не включена в чате, а вы не имеете прав модератора."
            )
            return

        try:
            url = f"{API_URL}/chat_members/{chat_id}"
            response_data = await fetch_json(url)
            members = response_data.get("members", [])
        except Exception as e:
            await message.reply(f"📛 Ошибка при получении участников: {str(e)}")
            return

        assert message.bot
        bot_id = (await message.bot.get_me()).id
        tags = [
            f'<a href="tg://user?id={member["user_id"]}">\u2060</a>'
            for member in members
            if member.get("user_id") and member["user_id"] != bot_id
        ]

        if not tags:
            await message.reply("❌ Нет участников для упоминания.")
            return

        chunk_size = 5
        chunks = [tags[i : i + chunk_size] for i in range(0, len(tags), chunk_size)]

        for idx, chunk in enumerate(chunks):
            tags_str = " ".join(chunk)
            if idx == 0:
                base_msg = await message.reply(
                    f"❗️ Упоминаю всех! {tags_str}", parse_mode=ParseMode.HTML
                )
            else:
                await base_msg.reply(f"⬆️⬆️⬆️ {tags_str}", parse_mode=ParseMode.HTML)
    except Exception:
        await error_report(message, bot, "tagall", traceback.format_exc())


@etc_router.message(Command("free_epic_games"), CooldownFilter("free_epic_games", 15))
async def cmd_epic_games(message: Message, bot: Bot):
    try:
        if not FREE_GAMES_PATH.exists():
            await message.reply("🤷‍♂️ Попробуйте позже")
            return

        with FREE_GAMES_PATH.open(encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                await message.reply("⚠️ Данные ещё не загружены. Попробуйте позже.")
                return
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                await message.reply(
                    "⚠️ Произошла ошибка при чтении данных. Обновление в процессе, попробуйте позже."
                )
                return
            available = data.get("available", {})
            unavailable = data.get("unavailable", {})
            updated_at = data.get("_updated_at")

        if not available and not unavailable:
            await message.reply(
                "🤷‍♀️ Сейчас нет бесплатных игр или данные не получены."
            )
            return

        msg_lines = []

        if available:
            msg_lines.append("🎁 <b>Бесплатно сейчас:</b>\n")
            for game in available.values():
                start = datetime.fromisoformat(game["start"]).strftime("%d.%m %H:%M")
                end = datetime.fromisoformat(game["end"]).strftime("%d.%m %H:%M")
                msg_lines.append(
                    f"🎮 <b>{game['title']}</b>\n"
                    f"🔗 <a href=\"{game['url']}\">Ссылка на игру</a>\n"
                    f"🗓️ <i>{start} UTC — {end} UTC</i>\n"
                    f"🆔 <code>{game['slug']}</code>\n"
                )

        if unavailable:
            msg_lines.append("\n🔒 <b>Не доступно в РФ:</b>\n")
            for game in unavailable.values():
                start = datetime.fromisoformat(game["start"]).strftime("%d.%m %H:%M")
                end = datetime.fromisoformat(game["end"]).strftime("%d.%m %H:%M")
                msg_lines.append(
                    f"🎮 <b>{game['title']}</b>\n"
                    f"🔗 <a href=\"{game['url']}\">Ссылка на игру</a>\n"
                    f"🗓️ <i>{start} UTC — {end}</i> UTC\n"
                    f"🆔 <code>{game['slug']}</code>\n"
                )

        if updated_at:
            dt = datetime.fromisoformat(updated_at)
            msg_lines.append(f"\n⌛️ Обновлено: {dt.strftime('%d.%m %H:%M UTC')}")

        await message.reply(
            "\n".join(msg_lines),
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "free_epic_games", traceback.format_exc())


@etc_router.callback_query(F.data == "ignore")
async def ignore_callback(query: CallbackQuery):
    await query.answer()
