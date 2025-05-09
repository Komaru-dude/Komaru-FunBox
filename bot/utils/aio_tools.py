from datetime import datetime, timedelta
import aiohttp
import uuid
import os
import logging
from aiogram import Bot
from aiogram.types import Message
from bot.utils.global_storage import error_report_lock, error_report_timestamps

API_HOST = "http://127.0.0.1:8001"


async def get_chat_owner_id(bot: Bot, chat_id: int):
    chat_administrators = await bot.get_chat_administrators(chat_id=chat_id)
    for admin in chat_administrators:
        if admin.status == "creator":
            return admin.user.id
    return None


async def get_user_id(message: Message) -> tuple[int | None, str | None]:
    text = message.text.strip() if message.text else ""
    error_msg = None

    if message.reply_to_message:
        return message.reply_to_message.from_user.id, None

    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention":
                return entity.user.id, None

            if entity.type == "mention":
                username = text[entity.offset : entity.offset + entity.length].lstrip(
                    "@"
                )
                data = await fetch_user_data(username=username)
                if data and "user_id" in data:
                    return data["user_id"], None
                error_msg = "Пользователь не найден"
                break

    if text:
        if text.isdigit():
            data = await fetch_user_data(user_id=int(text), chat_id=message.chat.id)
        else:
            username = text.lstrip("@")
            data = await fetch_user_data(username=username, chat_id=message.chat.id)
            if not data or "error" in data:
                data = await fetch_user_data(first_name=text, chat_id=message.chat.id)

        if data and "user_id" in data:
            return data["user_id"], None

    error_msg = error_msg or "Не указан пользователь"
    return None, error_msg


async def fetch_user_data(user_id=None, username=None, first_name=None, chat_id=None):
    try:
        if user_id and chat_id:
            # Проверяем существование пользователя в чате
            url = f"{API_HOST}/username/{chat_id}/{user_id}"
            username_data = await fetch_json(url)
            if "username" in username_data:
                first_name_data = await fetch_json(
                    f"{API_HOST}/first_name/{chat_id}/{user_id}"
                )
                return {
                    "user_id": user_id,
                    "username": username_data.get("username"),
                    "first_name": first_name_data.get("first_name", "Пользователь"),
                }
            return {"error": "Пользователь не найден в чате"}

        elif username:
            # Получаем user_id по username
            url = f"{API_HOST}/user/{username}"
            user_data = await fetch_json(url)
            if "user_id" in user_data:
                if chat_id:
                    first_name_data = await fetch_json(
                        f"{API_HOST}/first_name/{chat_id}/{user_data['user_id']}"
                    )
                    user_data["first_name"] = first_name_data.get(
                        "first_name", "Пользователь"
                    )
                return user_data
            return {"error": "Пользователь не найден"}

        elif first_name and chat_id:
            # Ищем пользователя по имени в чате
            url = f"{API_HOST}/chat_members/{chat_id}"
            members_data = await fetch_json(url)
            for member in members_data.get("members", []):
                if member.get("first_name") == first_name:
                    return {
                        "user_id": member["user_id"],
                        "username": member.get("username"),
                        "first_name": first_name,
                    }
            return {"error": "Пользователь с таким именем не найден"}

        return {"error": "Неверные параметры запроса"}

    except Exception as e:
        return {"error": f"Ошибка API: {str(e)}"}


async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"API Error: Status {response.status}")
            return await response.json()


async def make_post_request(url, payload, headers=None):
    async with aiohttp.ClientSession() as session:
        request_kwargs = {"json": payload}
        if headers is not None:
            request_kwargs["headers"] = headers

        async with session.post(url, **request_kwargs) as response:
            if response.status != 200 or not response.content:
                return None, f"❌ Ошибка API: статус {response.status}"
            try:
                return await response.json(), None
            except Exception as e:
                return None, f"❌ Ошибка обработки ответа: {str(e)}"


async def error_report(message: Message, bot: Bot, command, traceback):
    report_id = uuid.uuid4()
    current_time = datetime.now()
    send_to_user = True
    send_owner_alert = False

    async with error_report_lock:
        cutoff = current_time - timedelta(minutes=15)
        error_report_timestamps = [t for t in error_report_timestamps if t > cutoff]
        
        current_count = len(error_report_timestamps)
        if current_count >= 2:
            send_to_user = False
            send_owner_alert = current_count == 2
        
        error_report_timestamps.append(current_time)

    if send_to_user:
        await message.reply(
            f"❌ Возникла ошибка при обработке команды\n🔢 Report ID: {report_id}"
        )

        reply_info = (
            f"\n📦 Ответ на сообщение: {message.reply_to_message.text}"
            if message.reply_to_message
            else ""
        )
        error_report_text = (
            f"❌ Во время обработки команды {command} возникла ошибка!\n"
            f"🔢 Report ID: {report_id}\n💬 Сообщение пользователя: {message.text}{reply_info}\n\n"
            f"📛 Traceback:\n{traceback}"
        )

        chunks = [error_report_text[i:i+4096] for i in range(0, len(error_report_text), 4096)]
        for chunk in chunks:
            try:
                await bot.send_message(os.getenv("OWNER_ID"), chunk)
            except Exception as e:
                logging.error(f"Ошибка при отправке отчёта владельцу: {e}")

    elif send_owner_alert:
        alert_message = (
            f"⚠️ Слишком много ошибок! Получено 3+ отчетов за 15 минут.\n"
            f"Последний Report ID: {report_id}\n"
            f"Сообщение: {message.text[:300]}..."
        )
        try:
            await bot.send_message(os.getenv("OWNER_ID"), alert_message)
        except Exception as e:
            logging.error(f"Ошибка при отправке предупреждения: {e}")
