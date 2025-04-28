import asyncio
import os
import logging
from pyrogram import Client
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

load_dotenv()

api_id = os.getenv("API_ID")
api_hash = os.getenv("API_HASH")
token = os.getenv("BOT_API_TOKEN")

server = FastAPI()

app = (
    Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=token)
    if not os.path.exists("my_bot.session")
    else Client("my_bot")
)

logging.basicConfig(level=logging.INFO)


@server.get("/user/{username}")
async def get_user_id(username: str):
    """Получить user_id по username"""
    try:
        user = await app.get_users(username)
        return {"user_id": user.id}
    except Exception as e:
        logging.error(f"Ошибка при получении user_id для {username}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/username/{chat_id}/{user_id}")
async def get_username_by_id(chat_id: str, user_id: int):
    """Получить username по user_id и chat_id"""
    try:
        async for member in app.get_chat_members(chat_id):
            if member.user.id == user_id:
                return {"username": member.user.username}
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logging.error(
            f"Ошибка при получении username для {user_id} в чате {chat_id}: {e}"
        )
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/first_name/{chat_id}/{user_id}")
async def get_first_name_by_id(chat_id: str, user_id: int):
    """Получить first_name по user_id и chat_id"""
    try:
        async for member in app.get_chat_members(chat_id):
            if member.user.id == user_id:
                return {"first_name": member.user.first_name}
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logging.error(
            f"Ошибка при получении first_name для {user_id} в чате {chat_id}: {e}"
        )
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/chat_members/{chat_id}")
async def get_chat_members(chat_id: str):
    """Получить список участников чата"""
    try:
        members = []
        async for member in app.get_chat_members(chat_id):
            members.append(
                {
                    "user_id": member.user.id,
                    "username": member.user.username,
                    "first_name": member.user.first_name,
                }
            )
        return {"members": members}
    except Exception as e:
        logging.error(f"Ошибка при получении участников чата {chat_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


async def start_pyrogram():
    """Запуск Pyrogram-бота в фоне"""
    await app.start()
    logging.info("Pyrogram бот запущен.")
    await asyncio.Event().wait()


loop = asyncio.get_event_loop()
loop.create_task(start_pyrogram())
