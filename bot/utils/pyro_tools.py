import asyncio, os, logging
from pyrogram import Client
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
token = os.getenv("BOT_API_TOKEN")

if not api_id:
    raise ValueError("Ошибка: переменная API_ID не найдена. Убедитесь, что она присутствует в .env файле.")
if not api_hash:
    raise ValueError("Ошибка: переменная API_HASH не найдена. Убедитесь, что она присутствует в .env файле.")
if not token:
    raise ValueError("Ошибка: переменная BOT_API_TOKEN не найдена. Убедитесь, что она присутствует в .env файле.")

app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=token) if not os.path.exists("my_bot.session") else Client("my_bot")

server = FastAPI()

@server.get("/user/{username}")
async def get_user_id(username: str):
    try:
        user = await app.get_users(username)
        return {"user_id": user.id}
    except Exception as e:
        return {"error": str(e)}

@server.get("/username/{chat_id}/{user_id}")
async def get_username_by_id(chat_id: str, user_id: int):
    try:
        # Перебираем участников чата
        async for member in app.get_chat_members(chat_id):
            if member.user.id == user_id:
                return {"username": member.user.username}
        return {"error": "User not found"}
    except Exception as e:
        return {"error": str(e)}

@server.get("/first_name/{chat_id}/{user_id}")
async def get_first_name_by_id(chat_id: str, user_id: int):
    try:
        # Перебираем участников чата
        async for member in app.get_chat_members(chat_id):
            if member.user.id == user_id:
                return {"first_name": member.user.first_name}
        return {"error": "User not found"}
    except Exception as e:
        return {"error": str(e)}

async def start_pyrogram():
    """ Запуск Pyrogram-бота в фоне """
    await app.start()
    logging.info("Pyrogram бот запущен.")
    await asyncio.Event().wait()

loop = asyncio.get_event_loop()
loop.create_task(start_pyrogram())