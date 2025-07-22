import asyncio
import datetime
import html
import json
import os
import platform
import random
import re
import shutil
import traceback
from pathlib import Path

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message, URLInputFile
from aiohttp import ClientSession

from bot.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report, fetch_json
from bot.utils.global_storage import FREE_GAMES_PATH

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


@etc_router.message(Command("coffee"), CooldownFilter("418_cat", 604800))
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
            await message.reply(f"❌ Не удалось отправить кота: {e.message}")

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
            await message.reply(f"❌ Не удалось отправить собаку: {e.message}")

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


@etc_router.message(Command("weather"), CooldownFilter("weather", 150))
async def send_weather(message: Message, bot: Bot, db: Database):
    try:
        parts = message.text.strip().split(maxsplit=1)

        if len(parts) < 2:
            await message.reply(
                "❌ Вы не указали город.\nПример: <code>/weather Москва</code>",
                parse_mode=ParseMode.HTML,
            )
            await db.reset_cooldown(message.from_user.id, "weather")
            return

        city = parts[1]

        async with ClientSession() as session:
            url = f"https://api.weatherapi.com/v1/current.json?key={os.getenv('WEATHER_API_KEY')}&q={city}&aqi=yes"
            async with session.get(url) as response:
                if response.status == 400:
                    await message.reply("❌ Такой город не существует")
                    await db.reset_cooldown(message.from_user.id, "weather")
                    return
                elif response.status == 403:
                    await message.reply("❌ Упс, попробуйте позже")
                    await db.reset_cooldown(message.from_user.id, "weather")
                    return
                elif response.status == 401:
                    await message.reply(
                        "❌ Проблема с авторизацией\n\n🛠 Сообщение разработчику"
                    )
                    await db.reset_cooldown(message.from_user.id, "weather")
                    return

                data = await response.json()

        loc = data["location"]
        cur = data["current"]
        cond = cur["condition"]

        code = cond["code"]
        emoji = WEATHER_ICONS.get(code, "❔")

        text = (
            f"<b>{emoji} Погода в {loc['name']}, {loc['country']}</b>\n"
            f"<b>🌡 Температура:</b> {cur['temp_c']}°C (Ощущается как {cur['feelslike_c']}°C)\n"
            f"<b>💧 Влажность:</b> {cur['humidity']}%\n"
            f"<b>💨 Ветер:</b> {cur['wind_kph']} км/ч {cur['wind_dir']}\n"
            f"<b>👀 Видимость:</b> {cur['vis_km']} км\n"
            f"<b>🧪 Давление:</b> {cur['pressure_mb']} мбар\n"
            f"<b>🌞 UV-индекс:</b> {cur['uv']}\n"
            f"<b>💨 Качество воздуха (PM2.5):</b> {cur.get('air_quality', {}).get('pm2_5', 'н/д')}\n"
            f"<b>📅 Обновлено:</b> {cur['last_updated']}"
        )

        await message.reply(text, parse_mode=ParseMode.HTML)
    except Exception:
        await error_report(message, bot, "weather", traceback.format_exc())


@etc_router.message(Command("nillerxs"), CooldownFilter("bradok", 15))
async def cmd_nillerxs(message: Message):
    await message.reply("нильрекс")


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
            await message.reply(f"❌ Ошибка при получении участников: {str(e)}")
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
                "❌ Платформа не поддерживается\n📀 Требуется Linux + пакет cowsay"
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
                start = datetime.datetime.fromisoformat(game["start"]).strftime(
                    "%d.%m %H:%M"
                )
                end = datetime.datetime.fromisoformat(game["end"]).strftime(
                    "%d.%m %H:%M"
                )
                msg_lines.append(
                    f"🎮 <b>{game['title']}</b>\n"
                    f"🔗 <a href=\"{game['url']}\">Ссылка на игру</a>\n"
                    f"🗓️ <i>{start} UTC — {end} UTC</i>\n"
                    f"🆔 <code>{game['slug']}</code>\n"
                )

        if unavailable:
            msg_lines.append("\n🔒 <b>Не доступно в РФ:</b>\n")
            for game in unavailable.values():
                start = datetime.datetime.fromisoformat(game["start"]).strftime(
                    "%d.%m %H:%M"
                )
                end = datetime.datetime.fromisoformat(game["end"]).strftime(
                    "%d.%m %H:%M"
                )
                msg_lines.append(
                    f"🎮 <b>{game['title']}</b>\n"
                    f"🔗 <a href=\"{game['url']}\">Ссылка на игру</a>\n"
                    f"🗓️ <i>{start} UTC — {end}</i> UTC\n"
                    f"🆔 <code>{game['slug']}</code>\n"
                )

        if updated_at:
            dt = datetime.datetime.fromisoformat(updated_at)
            msg_lines.append(f"\n⌛️ Обновлено: {dt.strftime('%d.%m %H:%M UTC')}")

        await message.reply(
            "\n".join(msg_lines),
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "free_epic_games", traceback.format_exc())
