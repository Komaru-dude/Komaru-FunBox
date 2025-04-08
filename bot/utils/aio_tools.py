import aiohttp, os
from aiogram import Bot

ai_url = os.getenv("API_URL")

async def get_chat_owner_id(bot: Bot, chat_id: int):
    chat_administrators = await bot.get_chat_administrators(chat_id=chat_id)
    for admin in chat_administrators:
        if admin.status == 'creator':
            return admin.user.id
    return None

async def make_post_request(payload):
    async with aiohttp.ClientSession() as session:
        async with session.post(ai_url, json=payload) as response:
            if response.status != 200 or not response.content:
                return None, f"❌ Ошибка API: статус {response.status}, ответ пустой или ошибка сервера"
            try:
                data = await response.json()
                return data, None
            except Exception as e:
                return None, f"❌ Ошибка обработки ответа API: {str(e)}"