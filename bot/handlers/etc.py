import asyncio
import html
import json
import os
import platform
import random
import re
import shutil
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    URLInputFile,
)
from aiohttp import ClientSession

from bot import FREE_GAMES_PATH, logger
from bot.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report, fetch_json

etc_router = Router()


def load_http_codes(filename):
    path = Path(__file__).parent.parent / "media" / filename
    with open(path, "r") as f:
        return json.load(f)


cat_http_codes = load_http_codes("cat_http_codes.json")
dog_http_codes = load_http_codes("dog_http_codes.json")


WEATHER_ICONS = {
    1000: "☀️",
    1003: "⛅",
    1006: "☁️",
    1009: "🌥️",
    1030: "🌫️",
    1063: "🌦️",
    1066: "🌨️",
    1069: "🌧️",
    1072: "🌧️",
    1087: "⛈️",
    1114: "🌨️",
    1117: "❄️",
    1135: "🌁",
    1147: "🌁",
    1150: "🌧️",
    1153: "🌧️",
    1168: "🌧️",
    1171: "🌧️",
    1180: "🌧️",
    1183: "🌧️",
    1186: "🌧️",
    1189: "🌧️",
    1192: "🌧️",
    1195: "🌧️",
    1198: "🌧️",
    1201: "🌧️",
    1204: "🌨️",
    1207: "🌨️",
    1210: "🌨️",
    1213: "🌨️",
    1216: "🌨️",
    1219: "🌨️",
    1222: "🌨️",
    1225: "❄️",
    1237: "🌨️",
    1240: "🌦️",
    1243: "🌧️",
    1246: "🌧️",
    1249: "🌨️",
    1252: "🌨️",
    1255: "🌨️",
    1258: "❄️",
    1261: "🌨️",
    1264: "❄️",
    1273: "⛈️",
    1276: "⛈️",
    1279: "🌩️",
    1282: "⛈️",
}

WEATHER_CACHE = {}  # Хранит прогнозы на текущий день

BONUM_STICKER_ID = (
    "CAACAgIAAyEFAASbCRfOAAJW2mjT7S6mjNl2eq1K3OsShmsV2K8AAzotAAIEtJhLnn7lET7JhBM2BA"
)


@etc_router.message(Command("coffee"), CooldownFilter("418_cat", 604800, silent=True))
async def cmd_tea(message: Message, bot: Bot):
    try:

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
    except Exception:
        await error_report(message, bot, "coffee", traceback.format_exc())


@etc_router.message(Command("http_cat"), CooldownFilter("http_pets", 5))
async def cmd_http_cat(message: Message, bot: Bot):
    try:
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

    except Exception as e:
        await error_report(message, bot, "http_cat", traceback.format_exc())


@etc_router.message(Command("http_dog"), CooldownFilter("http_pets", 5))
async def cmd_http_dog(message: Message, bot: Bot):
    try:
        split_text = message.text.split()
        code = None

        if len(split_text) > 1:
            try:
                user_code = int(split_text[1])
                code = 405 if user_code == 418 else user_code
                if code not in dog_http_codes:
                    code = None
            except ValueError:
                pass

        code = code or random.choice(dog_http_codes)
        url = f"https://http.dog/{code}.jpg"

        try:
            await message.reply_photo(url, caption=f"Ваша HTTP собака: {code}")
        except TelegramBadRequest as e:
            await message.reply(f"📛 Не удалось отправить собаку: {e.message}")

    except Exception as e:
        await error_report(message, bot, "http_dog", traceback.format_exc())


@etc_router.message(Command("cat"), CooldownFilter("pets", 15))
async def cmd_cat(message: Message, bot: Bot):
    try:
        await message.reply_photo(
            URLInputFile("https://cataas.com/cat"), caption="🐈‍⬛ Ваш кот:"
        )
    except Exception:
        await error_report(message, bot, "cat", traceback.format_exc())


@etc_router.message(Command("cat_gif"), CooldownFilter("pets", 15))
async def cmd_cat_gif(message: Message, bot: Bot):
    try:
        await message.reply_video(URLInputFile("https://cataas.com/cat/gif"))
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


def create_days_keyboard(current_day_delta: int, user_id: int) -> InlineKeyboardMarkup:
    inline_keyboard = []
    nav_row = []

    if current_day_delta > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️", callback_data=f"weather:{current_day_delta - 1}:{user_id}"
            )
        )

    today_date = datetime.now()
    target_date = today_date + timedelta(days=current_day_delta)
    day_name = target_date.strftime("%a, %b %d")
    nav_row.append(
        InlineKeyboardButton(
            text=f"🗓 {day_name}",
            callback_data="ignore",
        )
    )

    if current_day_delta < 2:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️", callback_data=f"weather:{current_day_delta + 1}:{user_id}"
            )
        )

    inline_keyboard.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@etc_router.message(Command("weather"), CooldownFilter("weather", 150))
async def weather_command(message: Message, bot: Bot, db: Database):
    try:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await message.reply(
                "❌ Укажите город.\nПример: <code>/weather Москва</code>", parse_mode=ParseMode.HTML
            )
            await db.reset_cooldown(message.from_user.id, "weather")
            return
        city = parts[1]

        text, err = await fetch_weather(city, 0)
        if err:
            await message.reply(f"📛 Ошибка: {err}")
            await db.reset_cooldown(message.from_user.id, "weather")
            return

        keyboard = create_days_keyboard(0, message.from_user.id)
        await message.reply(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception:
        await error_report(message, bot, "weather", traceback.format_exc())


@etc_router.callback_query(F.data.startswith("weather:"))
async def weather_callback(query: CallbackQuery, bot: Bot):
    try:
        try:
            day_delta = int(query.data.split(":")[1])
        except (ValueError, IndexError):
            await query.answer("❌ Некорректный запрос", show_alert=True)
            return

        if query.data.split(":")[2] != query.from_user.id:
            await query.answer(
                "❌ Комару не разрешает отвечать на чужие колбэки", show_alert=True
            )
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

        keyboard = create_days_keyboard(day_delta)
        await query.message.edit_text(
            text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
        await query.answer()
    except Exception:
        await error_report(
            query.message, bot, "weather_callback", traceback.format_exc()
        )


@etc_router.message(Command("nillerxs"), CooldownFilter("bradok", 15))
async def cmd_nillerxs(message: Message):
    await message.reply("нильрекс")


@etc_router.message(Command("bonum"), CooldownFilter("bonum", 30, silent=True))
async def cmd_bonum(message: Message, bot: Bot):
    await bot.send_sticker(
        message.chat.id, BONUM_STICKER_ID, reply_to_message_id=message.message_id
    )


@etc_router.message(
    Command("tagall"),
    CooldownFilter("tagall", 900),
    ChatTypeFilter(["group", "supergroup"]),
)
async def cmd_tagall(message: Message, bot: Bot, db: Database):
    try:
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
            url = f"http://127.0.0.1:8001/chat_members/{chat_id}"
            response_data = await fetch_json(url)
            members = response_data.get("members", [])
        except Exception as e:
            await message.reply(f"📛 Ошибка при получении участников: {str(e)}")
            return

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
                await message.answer(
                    f"❗️ Упоминаю всех! {tags_str}", parse_mode=ParseMode.HTML
                )
            else:
                await message.answer(f"⬆️⬆️⬆️ {tags_str}", parse_mode=ParseMode.HTML)
    except Exception:
        await error_report(message, bot, "tagall", traceback.format_exc())


@etc_router.message(Command("cowsay"))
async def cmd_cowsay(message: Message, bot):
    try:
        if platform.system() != "Linux" or not shutil.which("cowsay"):
            await message.reply(
                "📛 Платформа не поддерживается\n📀 Требуется Linux + пакет cowsay"
            )
            return

        words = message.text.strip().split(maxsplit=1)

        if len(words) < 2 or not words[1].strip():
            if message.reply_to_message and message.reply_to_message.text:
                user_input = message.reply_to_message.text.strip()
            else:
                await message.reply(
                    "💬 Нужно указать текст (в сообщении или через ответ)"
                )
                return
        else:
            user_input = words[1].strip()

        safe_input = re.sub(
            r"[^a-zA-Zа-яА-Я0-9 .,!?()\\/_\-+=:;\"'`~@#№$%^&*]", "", user_input
        )
        safe_input = safe_input[:200]

        proc = await asyncio.create_subprocess_exec(
            "cowsay",
            "--",
            safe_input,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            await error_report(message, bot, "cowsay", stderr)
            return

        result = stdout.decode()
        await message.reply(
            f"<code>{html.escape(result)}</code>", parse_mode=ParseMode.HTML
        )

    except Exception:
        await error_report(message, bot, "cowsay", traceback.format_exc())


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
            await message.reply("🤷‍♀️ Сейчас нет бесплатных игр или данные не получены.")
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
