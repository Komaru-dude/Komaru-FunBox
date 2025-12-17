import os
import traceback
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.types import (
    CallbackQuery,
    ChatMemberUpdated,
    Message,
    TelegramObject,
    Update,
)

from bot import logger
from bot.database.database import Database


class ChatWatcher(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            bot: Bot = data["bot"]
            db: Database = data["db"]
            owner_id = os.getenv("OWNER_ID")

            actual_event = event
            if isinstance(event, Update):
                if event.message:
                    actual_event = event.message
                elif event.callback_query:
                    actual_event = event.callback_query
                elif event.my_chat_member:
                    actual_event = event.my_chat_member
            if isinstance(actual_event, ChatMemberUpdated):
                new_status = actual_event.new_chat_member.status

                if new_status in [ChatMemberStatus.KICKED, ChatMemberStatus.LEFT]:
                    user = actual_event.from_user
                    chat = actual_event.chat

                    if chat.type == "private":
                        msg = f"🗑 Пользователь заблокировал бота: <a href='tg://user?id={user.id}'>{user.full_name}</a> ({user.id})"
                        logger.info(f"User {user.id} blocked the bot.")
                    else:
                        msg = f"🗑 Бота кикнули из чата: <b>{chat.full_name}</b> ({chat.id}).\nКто: {user.full_name} ({user.id})"
                        logger.info(f"Bot kicked from chat {chat.id} by {user.id}")

                    if owner_id:
                        try:
                            await bot.send_message(
                                owner_id, msg, parse_mode=ParseMode.HTML
                            )
                        except:
                            pass

                return await handler(event, data)
            if isinstance(actual_event, CallbackQuery):
                return await handler(event, data)

            if isinstance(actual_event, Message):
                user = actual_event.from_user
                chat = actual_event.chat
                text = actual_event.text or ""
                chat_type = chat.type
                is_bot_command = False

                bot_obj = await bot.me()
                bot_username = bot_obj.username.lower()

                if text and actual_event.entities:
                    for entity in actual_event.entities:
                        if entity.type == "bot_command":
                            command = text[
                                entity.offset : entity.offset + entity.length
                            ].lower()
                            if "@" in command:
                                cmd, mentioned_bot = command.split("@", 1)
                                if mentioned_bot == bot_username:
                                    is_bot_command = True
                                    break
                            else:
                                if chat_type == "private":
                                    is_bot_command = True
                                    break

                user_id = user.id
                chat_id = chat.id
                chat_name = chat.full_name
                user_name = user.full_name
                language_code = user.language_code

                if not await db.chat_exists(chat_id):
                    await db.add_chat(chat_id, chat_data={"type": chat_type})
                    await db.init_chat_settings(chat_id)
                    if chat_type != "private":
                        msg = f"🔔 Новый чат: {chat_id}, имя: {chat_name}"
                        logger.info(msg)
                        if owner_id:
                            await bot.send_message(owner_id, msg)
                            if chat.username:
                                link = f"https://t.me/{chat.username}"
                                await bot.send_message(owner_id, f"🔗 Ссылка: {link}")

                if chat_type == "private" or is_bot_command:
                    await db.log_command()
                    if not await db.user_exists(user_id, chat_id):
                        await db.add_user(user_id, chat_id)
                    if not await db.get_global_user(user_id):
                        await db.add_global_user(
                            user_id, {"language_code": language_code, "name": user_name}
                        )
                        msg = f'🔔 Новый пользователь: <a href="tg://user?id={user_id}">{user_id}</a>, {user_name}'
                        logger.info(msg)
                        if owner_id:
                            await bot.send_message(
                                owner_id, msg, parse_mode=ParseMode.HTML
                            )

            return await handler(event, data)

        except Exception:
            logger.error("❌ Ошибка в ChatWatcher:", exc_info=True)
            if owner_id := os.getenv("OWNER_ID"):
                try:
                    await bot.send_message(
                        owner_id,
                        f"❌ Ошибка в ChatWatcher:\n\n{traceback.format_exc()}",
                    )
                except:
                    pass
            return await handler(event, data)
