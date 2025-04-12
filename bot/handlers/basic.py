import random, aiohttp, os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

base_router = Router()
current_dir = os.path.dirname(os.path.abspath(__file__))
media_folder = os.path.join(current_dir, '..', 'media')
sticker_extensions = {".webp", ".tgs", ".webm"}
API_URL = "http://127.0.0.1:8001"

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка API: статус {response.status}")
            return await response.json()

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет!\n"
                        "Это универсальный развлекательный бот.\n"
                        "Если хочешь узнать более подробную информацию о командах: /help")
    
@base_router.message(Command("random"))
async def cmd_random(message: Message):
    responses = [
        "Да, без сомнений!",
        "Нет, это не сбудется.",
        "Возможно, ты прав.",
        "Скорее всего, да.",
        "Попробуй снова позже.",
        "Определенно нет.",
        "Я бы сказал да.",
    ]
    response = random.choice(responses)
    await message.reply(response)

@base_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    state = await state.get_state()
    if state is None:
        await message.reply("А чего отменять то?")
    else:
        await state.clear()
        await message.reply("❌ Отменено")

@base_router.message(Command('privetbradok'))
async def cmd_privebradok(message: Message):
    target_id = None
    first_name = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
        first_name = message.reply_to_message.from_user.first_name
    else:
        text = message.text
        split_text = text.split(maxsplit=1)

        if len(split_text) > 1 and split_text[1].startswith("@"):
            username = split_text[1][1:]
            try:
                data = await fetch_json(f"{API_URL}/user/{username}")

                if "user_id" in data:
                    target_id = data["user_id"]
                    name_data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                    first_name = name_data.get("first_name", "Неизвестный")
                else:
                    await message.reply(f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}")
                    return

            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = split_text[1]
            try:
                data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply("Укажите пользователя через реплай, @username или айди.")
            return

    user2_link = f'<a href="tg://user?id={target_id}">{first_name}</a>'

    stick = random.choice([True, False])

    if message.reply_to_message and not stick:
         await message.reply_to_message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
    elif not stick:
        await message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
    else:
        stickers = [f for f in os.listdir(media_folder) if os.path.splitext(f)[1].lower() in sticker_extensions]
        if not stickers:
            raise FileNotFoundError("Нет стикеров в ../media")
        random_stick = random.choice(stickers)
        sticker = FSInputFile(os.path.join(media_folder, random_stick))
        if message.reply_to_message:
            await message.reply_to_message.reply_sticker(sticker)
        else:
            await message.reply_sticker(sticker)

@base_router.message(Command("say"))
async def cmd_say(message: Message):
    split_text = message.text.split(maxsplit=1)
    if len(split_text) > 1:
        await message.answer(split_text[1])
        try:
            await message.delete()
        except:
            await message.answer("Брадочки, оформите права на удаление сообщений 😢")
    else:
        await message.reply("А что говорить то?")