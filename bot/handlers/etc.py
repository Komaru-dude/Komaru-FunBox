import random
import traceback
import json
import re
import os
from pathlib import Path
from urllib.parse import quote_plus
from aiohttp import ClientSession
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, URLInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.chat_type import ChatTypeFilter
from bot.utils.aio_tools import error_report, fetch_json

etc_router = Router()
current_dir = os.path.dirname(os.path.abspath(__file__))
media_folder = os.path.join(current_dir, "..", "media")
sticker_extensions = {".webp", ".tgs", ".webm"}


def load_http_codes(filename):
    path = Path(__file__).parent.parent / "media" / filename
    with open(path, "r") as f:
        return json.load(f)


cat_http_codes = load_http_codes("cat_http_codes.json")
dog_http_codes = load_http_codes("dog_http_codes.json")


@etc_router.message(Command("coffee"), CooldownFilter("418_cat", 604800))
async def cmd_tea(message: Message, bot: Bot, db: Database):
    try:
        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

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
async def cmd_http_cat(message: Message, bot: Bot, db: Database):
    try:
        split_text = message.text.split()
        code = None

        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

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
async def cmd_http_dog(message: Message, bot: Bot, db: Database):
    try:
        split_text = message.text.split()
        code = None

        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

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
async def cmd_cat(message: Message, bot: Bot, db: Database):
    try:
        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        await message.reply_photo(
            URLInputFile("https://cataas.com/cat"), caption="🐈‍⬛ Ваш кот:"
        )
    except Exception:
        await error_report(message, bot, "cat", traceback.format_exc())


@etc_router.message(Command("cat_gif"), CooldownFilter("pets", 15))
async def cmd_cat_gif(message: Message, bot: Bot, db: Database):
    try:
        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return
        await message.reply_video(URLInputFile("https://cataas.com/cat/gif"))
    except Exception:
        await error_report(message, bot, "cat_gif", traceback.format_exc())


@etc_router.message(Command("weather"), CooldownFilter("weather", 150))
async def send_weather(message: Message):
    def escape_ansi(line):
        ansi_escape = re.compile(r"(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]")
        return ansi_escape.sub("", line)

    parts = message.text.split()
    location = parts[1] if len(parts) > 1 else "Oymyakon"
    if len(parts) <= 1:
        await message.reply("⚠️ Вы не указали город, будет использоваться Oymyakon")

    lang = (
        "ru"
        if location and location[0].lower() in "ёйцукенгшщзхъфывапролджэячсмитьбю"
        else "en"
    )

    encoded_location = quote_plus(location)
    url = f"https://wttr.in/{encoded_location}?m&T0&lang={lang}"

    async with ClientSession() as session:
        async with session.get(url) as response:
            weather_art = await response.text()
            cleaned_art = escape_ansi(weather_art)
            await message.reply(
                f"<code>{cleaned_art}</code>", parse_mode=ParseMode.HTML
            )


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

        if not await db.is_feature_enabled(
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
