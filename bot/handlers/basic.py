import random, requests, os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

base_router = Router()
API_URL = "http://127.0.0.1:8001"

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет!\n"
                        "Это развлекательный бот созданный для кочон подвала.\n"
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
    
    await message.answer(response)

@base_router.message(Command("cancel"))
@base_router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Процесс добавления команды отменен")

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
                response = requests.get(f"{API_URL}/user/{username}")
                data = response.json()

                if "user_id" in data:
                    target_id = data["user_id"]

                    response_name = requests.get(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                    name_data = response_name.json()

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
                chat_id = message.chat.id
                response = requests.get(f"{API_URL}/first_name/{chat_id}/{target_id}")
                data = response.json()
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply("Укажите пользователя через реплай, @username или айди.")
            return
    user2_link = f'<a href="tg://user?id={target_id}">{first_name}</a>'

    if message.reply_to_message:
         await message.reply_to_message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
    else:
        await message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
