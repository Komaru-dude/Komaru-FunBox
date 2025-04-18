import random
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, URLInputFile
from aiogram.enums import ParseMode
from pathlib import Path

easter_router = Router()

# Список HTTP-кодов, для которых доступны изображения на http.cat
cat_http_codes = [
    100, 101, 102, 103, 200, 201, 202, 203, 204, 205, 206, 207, 208, 214, 226,
    300, 301, 302, 303, 304, 305, 307, 308, 400, 401, 402, 403, 404, 405, 406,
    407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 419, 420, 421, 422,
    423, 424, 425, 426, 428, 429, 431, 444, 450, 451, 495, 496, 497, 498, 499,
    500, 501, 502, 503, 504, 506, 507, 508, 509, 510, 511, 521, 522, 523, 525,
    530, 599
]
dog_http_codes = [  # А это для http.dog
    100, 101, 102, 103, 200, 201, 202, 203, 204, 205, 206, 207, 208, 218, 226,
    300, 301, 302, 303, 304, 305, 306, 307, 308, 400, 401, 402, 403, 404, 405,
    406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 419, 420, 421,
    422, 423, 424, 425, 426, 428, 429, 430, 431, 440, 444, 449, 451, 460, 463,
    464, 494, 495, 496, 497, 498, 499, 500, 501, 502, 503, 504, 505, 506, 507,
    508, 509, 510, 511, 520, 521, 522, 523, 524, 525, 526, 527, 529, 530, 561,
    598, 599, 999
]

@easter_router.message(Command("coffee"))
async def cmd_tea(message: Message):
    file_path = Path(__file__).parent.parent / 'media' / '418.jpg'
    t418 = FSInputFile(file_path)
    if message.reply_to_message:
        await message.reply_to_message.reply_photo(t418, caption="418 I'm a <a href='https://ru.wikipedia.org/wiki/HTCPCP'>teapot</a> ☕", parse_mode=ParseMode.HTML)
    else:
        await message.reply_photo(t418, caption="418 I'm a <a href='https://ru.wikipedia.org/wiki/HTCPCP'>teapot</a> ☕", parse_mode=ParseMode.HTML)

@easter_router.message(Command("http_cat"))
async def cmd_http_cat(message: Message):
    code = random.choice(cat_http_codes)
    url = f"https://http.cat/{code}.jpg"
    image = URLInputFile(url=url, filename=f"{code}.jpg")
    await message.reply_photo(photo=image, caption=f"Ваш HTTP кот: {code}")

@easter_router.message(Command("http_dog"))
async def cmd_http_dog(message: Message):
    code = random.choice(dog_http_codes)
    url = f"https://http.dog/{code}.jpg"
    image = URLInputFile(url=url, filename=f"{code}.jpg")
    await message.reply_photo(photo=image, caption=f"Ваша HTTP собака: {code}")

@easter_router.message(Command("cat"))
async def cmd_cat(message: Message):
    cat = URLInputFile("https://cataas.com/cat")
    await message.reply_photo(cat, caption="🐈‍⬛ Ваш кот:")

@easter_router.message(Command("cat_gif"))
async def cmd_cat_gif(message: Message):
    cat = URLInputFile("https://cataas.com/cat/gif")
    await message.reply_video(cat)