import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import GetParticipantRequest

try:
    from bot import logger
except ImportError:
    import logging

    logger = logging.getLogger("uvicorn")

load_dotenv()

api_id = int(os.getenv("API_ID") or 0)
api_hash = os.getenv("API_HASH") or ""
token = os.getenv("BOT_API_TOKEN")

app = TelegramClient("my_bot", api_id, api_hash)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    try:
        if token:
            await app.start(bot_token=token)  # type: ignore
        else:
            await app.start()  # type: ignore
        logger.info("📡 Telethon клиент запущен.")
    except Exception as e:
        logger.error(f"Критическая ошибка при старте Telethon клиента: {e}")
        raise e

    yield

    logger.info("🛑 Останавливаем Telethon клиент...")
    await app.disconnect()  # type: ignore
    logger.info("🔒 Telethon клиент отключен.")


server = FastAPI(lifespan=lifespan)


async def ensure_client_started():
    if not app.is_connected():
        logger.warning("Telethon потерял соединение. Переподключаемся...")
        await app.connect()


@server.get("/user/{username}")
async def get_user_id(username: str):
    """Получить user_id по username"""
    try:
        await ensure_client_started()
        user = await app.get_entity(username)
        return {"user_id": user.id}
    except Exception as e:
        logger.error(f"Ошибка при получении user_id для {username}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/username/{chat_id}/{user_id}")
async def get_username_by_id(chat_id: int, user_id: int):
    """Получить username по user_id и chat_id"""
    try:
        await ensure_client_started()
        chat = await app.get_entity(chat_id)
        user = await app.get_entity(user_id)

        try:
            participant = await app(
                GetParticipantRequest(channel=chat, participant=user)
            )
            if participant:
                return {"username": user.username}
        except errors.UserNotParticipantError:
            logger.warning(f"Пользователь {user_id} не найден в чате {chat_id}.")
            raise HTTPException(status_code=404, detail="User not found in chat.")
        except Exception as e:
            logger.warning(
                f"Пользователь {user_id} не является участником чата {chat_id}: {e}"
            )
            raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Ошибка при получении username для {user_id} в чате {chat_id}: {e}"
        )
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/first_name/{chat_id}/{user_id}")
async def get_first_name_by_id(chat_id: int, user_id: int):
    """Получить first_name по user_id и chat_id"""
    try:
        await ensure_client_started()
        participants = await app.get_participants(chat_id, limit=None)
        for member in participants:
            if member.id == user_id:
                return {"first_name": getattr(member, "first_name", None)}
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error(
            f"Ошибка при получении first_name для {user_id} в чате {chat_id}: {e}"
        )
        raise HTTPException(status_code=400, detail=str(e))


@server.get("/chat_members/{chat_id}")
async def get_chat_members(chat_id: int):
    """Получить список участников чата"""
    try:
        await ensure_client_started()
        members = []
        participants = await app.get_participants(chat_id, limit=None)
        for member in participants:
            members.append(
                {
                    "user_id": member.id,
                    "username": getattr(member, "username", None),
                    "first_name": getattr(member, "first_name", None),
                }
            )
        return {"members": members}
    except Exception as e:
        logger.error(f"Ошибка при получении участников чата {chat_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
