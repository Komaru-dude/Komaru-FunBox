import random
import traceback
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, URLInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import db
from bot.utils.aio_tools import error_report

easter_router = Router()

cat_http_codes = [
    100, 101, 102, 103,
    200, 201, 202, 203, 204, 205, 206, 207, 208, 214, 226,
    300, 301, 302, 303, 304, 305, 307, 308,
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 
    412, 413, 414, 415, 416, 417, 419, 420, 421, 422, 423, 424, 
    425, 426, 428, 429, 431, 444, 450, 451, 495, 496, 497, 498, 
    499, 500, 501, 502, 503, 504, 506, 507, 508, 509, 510, 511, 
    521, 522, 523, 525, 530, 599,
]

dog_http_codes = [
    100, 101, 102, 103,
    200, 201, 202, 203, 204, 205, 206, 207, 208, 218, 226,
    300, 301, 302, 303, 305, 306, 307, 308,
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 
    412, 413, 414, 415, 416, 417, 419, 420, 421, 422, 423, 424, 
    425, 426, 428, 429, 430, 431, 440, 444, 449, 451, 460, 463, 
    464, 494, 495, 496, 497, 498, 499, 500, 501, 502, 503, 504, 
    505, 506, 507, 508, 509, 510, 511, 520, 521, 522, 523, 524, 
    525, 526, 527, 529, 530, 561, 598, 599, 999,
]


@easter_router.message(Command("coffee"))
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


@easter_router.message(Command("http_cat"))
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


@easter_router.message(Command("http_dog"))
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


@easter_router.message(Command("cat"))
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


@easter_router.message(Command("cat_gif"))
async def cmd_cat_gif(message: Message, bot: Bot):
    try:
        if db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return
        await message.reply_video(URLInputFile("https://cataas.com/cat/gif"))
    except Exception:
        await error_report(message, bot, "cat_gif", traceback.format_exc())
