import asyncio
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pyrogram.client import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant

from bot import logger

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


@server.get("/user/{username}")
async def get_user_id(username: str):
    """Получить user_id по username"""
    try:
        user = await app.get_users(username)
        return {"user_id": user.id}
    except Exception as e:
        logger.error(f"Ошибка при получении user_id для {username}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/username/{chat_id}/{user_id}")
async def get_username_by_id(chat_id: str, user_id: int):
    """Получить username по user_id и chat_id"""
    try:
        chat_member = await app.get_chat_member(chat_id, user_id)

        if chat_member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.RESTRICTED,
        ]:
            return {"username": chat_member.user.username}
        else:
            logger.warning(
                f"Пользователь {user_id} в чате {chat_id} не является активным членом. Статус: {chat_member.status}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"User not an active participant: {chat_member.status}",
            )
    except UserNotParticipant:
        logger.warning(
            f"Пользователь {user_id} не найден в чате {chat_id} (через прямой запрос Pyrogram)."
        )
        raise HTTPException(status_code=404, detail="User not found in chat.")
    except Exception as e:
        logger.error(
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
        logger.error(
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
        logger.error(f"Ошибка при получении участников чата {chat_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


async def start_pyrogram():
    """Запуск Pyrogram-бота в фоне"""
    await app.start()
    logger.info("📡 Pyrogram бот запущен.")
    await asyncio.Event().wait()


loop = asyncio.get_event_loop()
loop.create_task(start_pyrogram())
