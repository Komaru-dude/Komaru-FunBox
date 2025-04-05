import requests
import os
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, URLInputFile

ai_router = Router()
url = os.getenv("API_URL")

@ai_router.message(Command("gpt"))
async def cmd_gpt(message: Message):
    base_msg = await message.reply("🔄 Обработка...")
    request = message.text.split(maxsplit=1)

    if len(request) < 2:
        await base_msg.edit_text("❌ Пожалуйста, укажите сообщение для нейросети.")
        return

    payload = {
        "model": "gpt-4",
        "request": {
            "messages": [{"role": "user", "content": request[1]}]
        }
    }

    try:
        response = requests.post(url, json=payload)

        if response.status_code != 200 or not response.content:
            await base_msg.edit_text(f"❌ Ошибка API: статус {response.status_code}, ответ пустой или ошибка сервера")
            return

        data = response.json()
        answer = data.get("answer", "⚠️ Ошибка: нет ответа от API")
        await base_msg.edit_text(f"💭 Запрос: {request[1]}\n\n🧠 Ответ нейросети: {answer}")

    except requests.RequestException as e:
        await base_msg.edit_text(f"❌ Ошибка запроса: {e}")

@ai_router.message(Command("image"))
async def cmd_img(message: Message):
    base_msg = await message.reply("🔄 Обработка...")
    request = message.text.split(maxsplit=1)

    if len(request) < 2:
        await base_msg.edit_text("❌ Пожалуйста, укажите сообщение для нейросети.")
        return

    payload = {
        "model": "flux",
        "request": {
            "messages": [{"content": request[1]}]
        }
    }

    try:
        response = requests.post(url, json=payload)

        if response.status_code != 200 or not response.content:
            await base_msg.edit_text(f"❌ Ошибка API: статус {response.status_code}, ответ пустой или ошибка сервера")
            return

        data = response.json()
        answer_list = data.get("answer")

        if not answer_list:
            await base_msg.edit_text("⚠️ Ошибка: нет ответа от API")
            return

        image_url = answer_list[0]

        image_input = URLInputFile(image_url)
        await message.answer_photo(image_input, caption="🖼️ Сгенерированное изображение")

        await base_msg.delete()

    except requests.RequestException as e:
        await base_msg.edit_text(f"❌ Ошибка запроса: {e}")