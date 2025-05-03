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
from bot import db
from bot.utils.aio_tools import error_report

etc_router = Router()
API_URL = "http://127.0.0.1:8001"
current_dir = os.path.dirname(os.path.abspath(__file__))
media_folder = os.path.join(current_dir, "..", "media")
sticker_extensions = {".webp", ".tgs", ".webm"}


def load_http_codes(filename):
    path = Path(__file__).parent.parent / "media" / filename
    with open(path, "r") as f:
        return json.load(f)


cat_http_codes = load_http_codes("cat_http_codes.json")
dog_http_codes = load_http_codes("dog_http_codes.json")


@etc_router.message(Command("coffee"))
async def cmd_tea(message: Message, bot: Bot):
    try:
        if db.is_user_mediabanned(message.from_user.id):
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


@etc_router.message(Command("http_cat"))
async def cmd_http_cat(message: Message, bot: Bot):
    try:
        split_text = message.text.split()
        code = None

        if db.is_user_mediabanned(message.from_user.id):
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


@etc_router.message(Command("http_dog"))
async def cmd_http_dog(message: Message, bot: Bot):
    try:
        split_text = message.text.split()
        code = None

        if db.is_user_mediabanned(message.from_user.id):
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


@etc_router.message(Command("cat"))
async def cmd_cat(message: Message, bot: Bot):
    try:
        if db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        await message.reply_photo(
            URLInputFile("https://cataas.com/cat"), caption="🐈‍⬛ Ваш кот:"
        )
    except Exception:
        await error_report(message, bot, "cat", traceback.format_exc())


@etc_router.message(Command("cat_gif"))
async def cmd_cat_gif(message: Message, bot: Bot):
    try:
        if db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return
        await message.reply_video(URLInputFile("https://cataas.com/cat/gif"))
    except Exception:
        await error_report(message, bot, "cat_gif", traceback.format_exc())


@etc_router.message(Command("shutter"))
async def cmd_shutter(message: Message, bot: Bot):
    try:

        def generate_stutter(word):
            if len(word) < 2 or not word[0].isalpha():
                return word

            stutter_type = random.choice(
                [
                    "repeat",
                    "repeat",
                    "hyphenated",
                    "double_hyphen",
                    "ellipsis",
                    "spacey",
                    "mixed_case",
                ]
            )

            repeats = random.randint(1, 3)
            first_letter = (
                word[0].upper() if random.choice([True, False]) else word[0].lower()
            )
            second_letter = (
                word[1].lower() if random.choice([True, False]) else word[1].upper()
            )

            if random.random() < 0.3:
                interjections = ["м-м", "э-э", "х-х", "а-а", "з-з"]
                word = f"{random.choice(interjections)}... {word}"

            if stutter_type == "repeat":
                parts = [f"{first_letter}-" * repeats + word]
            elif stutter_type == "hyphenated":
                parts = [f"{first_letter}-{second_letter}-{word}"]
            elif stutter_type == "double_hyphen":
                parts = [f"{first_letter}--{second_letter}--{word}"]
            elif stutter_type == "ellipsis":
                parts = [f"{first_letter}...{second_letter}...{word}"]
            elif stutter_type == "spacey":
                parts = [f"{first_letter} {second_letter} {word}"]
            elif stutter_type == "mixed_case":
                parts = [f"{first_letter.lower()}-{second_letter.upper()}-{word}"]

            if random.random() < 0.2:
                parts.append("...")

            return "".join(parts)

        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
        else:
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.reply("❌ А что конвертировать?")
                return
            text = parts[1]

        words = text.split()
        result = []

        emojis = ["😅", "🤔", "🙄", "😬", "😶", "🤷"]

        for word in words:
            if random.random() < 0.4:
                stuttered = generate_stutter(word)

                if random.random() < 0.4:
                    stuttered = stuttered.replace(" ", f" {random.choice(emojis)} ", 1)

                result.append(stuttered)
            else:
                result.append(word)

            if random.random() < 0.2:
                result.append(random.choice(emojis))

        final_text = " ".join(result)

        suffixes = [
            f"~~ {random.choice(emojis)}",
            f"/// {random.choice(emojis)}",
            f"☆*:.｡.o(≧▽≦)o.｡.:*☆",
            f"{random.choice(['~', '*', ''])} {random.choice(emojis)} {random.choice(emojis)}",
            "(｡♥‿♥｡)",
            "(≧◡≦) ♡",
            "(｡•́‿•̀｡)ฅ",
            "(^•ﻌ•^) ฅ",
            "(๑>◡<๑)",
            "(づ｡◕‿‿◕｡)づ",
            "(*≧ω≦)",
            "(ღ✪v✪)｡o♡",
            "(U ᵕ U❁)",
            "(๑˃ᴗ˂)ﻭ",
            "(*°▽°*)",
            "(✿◠‿◠)",
            "(ฅ^•ﻌ•^ฅ)",
            "♡＾▽＾♡",
            "(๑ᴖ◡ᴖ๑)",
            "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
            "(ʘ‿ʘ)✿",
            "(◕‿◕✿)",
            "(✧ω✧)",
            "(๑´• .̫ • `๑)",
            "(っ˘ω˘ς )",
            "(*ฅ́˘ฅ̀*)♡",
            "(つ≧▽≦)つ",
            "(◍•ᴗ•◍)♡",
            "✧(＾◡＾)✿",
        ]

        if random.random() < 0.2:
            prefixes = ["А-а... ", "Э-э... ", "М-м... ", "Ну..."]
            final_text = random.choice(prefixes) + final_text

        final_text += f" {random.choice(suffixes)}"

        if random.random() < 0.25:
            final_text += random.choice(["...", "..~~", "……"])

        if len(final_text) > 4096:
            chunks = [final_text[i : i + 4096] for i in range(0, len(final_text), 4096)]
        else:
            chunks = [final_text]
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                await message.reply(chunk)
            else:
                await message.answer(chunk)
    except Exception:
        await error_report(message, bot, "shutter", traceback.format_exc())


@etc_router.message(Command("weather"))
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
