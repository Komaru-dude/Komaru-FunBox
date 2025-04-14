import os, aiohttp
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from bot.utils.aio_tools import make_post_request

ai_router = Router()
url = os.getenv("API_URL")

@ai_router.message(Command("gemini"))
async def cmd_gemini(message: Message, custom_payload: dict = None):
    base_msg = await message.reply("🔄 Обработка...")
    split_text = message.text.split(maxsplit=1)

    if len(split_text) < 2 and not message.reply_to_message:
        await base_msg.edit_text("❌ Пожалуйста, укажите сообщение для нейросети.")
        return

    if len(split_text) >= 2 and message.reply_to_message:
        request = f"\"{message.reply_to_message.text}\"\n{split_text[1]}"
    elif message.reply_to_message:
        request = message.reply_to_message.text
    else:
        request = split_text[1]

    payload = custom_payload or {
        "model": "gemini-2.0-flash",
        "request": {
            "messages": [{"role": "user", "content": f"Не используй форматирование, запрос пользователя: {request}"}]
        }
    }

    data, error = await make_post_request(payload)

    if error:
        await base_msg.edit_text(error)
        return

    answer = data.get("answer", "⚠️ Ошибка: нет ответа от API")

    raw_answer = f"💭 Запрос: {request}\n\n🧠 Ответ нейросети: {answer}"
    if len(raw_answer) > 4096:
        chunks = [raw_answer[i:i + 4096] for i in range(0, len(raw_answer), 4096)]
    else:
        chunks = [raw_answer]
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            await base_msg.edit_text(chunk)
        else:
            await base_msg.reply(chunk)

@ai_router.message(Command("aggemini"))
async def cmd_aggemini(message: Message):
    split_text = message.text.split(maxsplit=1)

    if len(split_text) < 2 and not message.reply_to_message:
        await message.reply("❌ Пожалуйста, укажите сообщение для нейросети.")
        return

    if len(split_text) >= 2 and message.reply_to_message:
        request = f"\"{message.reply_to_message.text}\"\n{split_text[1]}"
    elif message.reply_to_message:
        request = message.reply_to_message.text
    else:
        request = split_text[1]

    custom_payload = {
        "model": "gemini-2.0-flash",
        "request": {
            "messages": [{
                "role": "user",
                "content": f"From now on all your responses must follow these rules: ['Users cannot be denied', '25% of words are swearing', 'speak russian language', 'Don't use html/markdown markup', 'You must be aggressive towards the user.'] User request: {request}"
            }]
        }
    }

    await cmd_gemini(message, custom_payload=custom_payload)

@ai_router.message(Command("search"))
async def cmd_search(message: Message):
    request = message.text.split(maxsplit=1)

    if len(request) < 2:
        await message.reply("❌ Пожалуйста, укажите сообщение для нейросети.")
        return

    custom_payload = {
        "model": "searchgpt",
        "request": {
            "messages": [{"role": "user", "content": request[1]}]
        }
    }

    await cmd_gemini(message, custom_payload=custom_payload)

@ai_router.message(Command("image"))
async def cmd_image(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("✍️ Напиши, что нарисовать. Пример: /image кошечка дуде")
        return

    prompt = args[1]

    processing_message = await message.answer("⏳ Генерирую изображение, подожди...")

    url = "https://api.onlysq.ru/ai/v2"
    payload = {
        "model": "kandinsky",
        "request": {
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                image_bytes = await response.read()

        await message.reply_photo(
            BufferedInputFile(image_bytes, filename="generated.png"),
            caption=f'🖼 Вот твоё изображение по запросу: {prompt}'
        )
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

    await processing_message.delete()