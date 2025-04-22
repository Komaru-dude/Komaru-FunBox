import aiohttp, os
from aiogram import Bot
from aiogram.types import Message

ai_url = os.getenv("API_URL")

async def get_chat_owner_id(bot: Bot, chat_id: int):
    chat_administrators = await bot.get_chat_administrators(chat_id=chat_id)
    for admin in chat_administrators:
        if admin.status == 'creator':
            return admin.user.id
    return None

async def get_user(message: Message):
    text = message.text.strip()
    error_msg = None
    first_name = "Пользователь"

    if message.reply_to_message:
        user = message.reply_to_message.from_user
        return user.id, user.first_name or first_name, None

    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                user = entity.user
                return user.id, user.first_name or first_name, None
            
            if entity.type == "mention":
                username = text[entity.offset:entity.offset+entity.length].lstrip('@')
                data = await fetch_user_data(username=username)
                if data: 
                    return data['user_id'], data.get('first_name', first_name), None
                break

    if text.isdigit():
        data = await fetch_user_data(user_id=int(text), chat_id=message.chat.id)
    else:
        data = await fetch_user_data(username=text.lstrip('@'), chat_id=message.chat.id)

    if data and data.get('user_id'):
        return data['user_id'], data.get('first_name', first_name), None

    error_msg = data.get('error') if data else "Не указан пользователь"
    await message.reply(f"Ошибка: {error_msg}")
    return None, None, error_msg

async def fetch_user_data(user_id=None, username=None, chat_id=None):
    try:
        if user_id:
            url = f'http://127.0.0.1:8001/username/{chat_id}/{user_id}'
        elif username:
            url = f'http://127.0.0.1:8001/user/{username}'
        else:
            return {'error': 'Invalid parameters'}

        data = await fetch_json(url)
        if data.get('user_id'):
            data['first_name'] = await get_first_name(chat_id, data['user_id'])
        return data

    except Exception as e:
        return {'error': f'API Error: {str(e)}'}

async def get_first_name(chat_id, user_id):
    try:
        data = await fetch_json(f'http://127.0.0.1:8001/first_name/{chat_id}/{user_id}')
        return data.get('first_name', 'Пользователь')
    except:
        return 'Пользователь'

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка API: статус {response.status}")
            return await response.json()

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