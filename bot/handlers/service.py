from traceback import format_exc

from aiogram import Bot, F, Router
from aiogram.filters.chat_member_updated import (
    IS_MEMBER,
    IS_NOT_MEMBER,
    ChatMemberUpdatedFilter, MEMBER, KICKED
)
from aiogram.types import ChatMemberUpdated, Message

from bot.database import Database
from bot.filters.func_filter import FuncEnabled
from bot.utils.aio_tools import error_report

service_router = Router()
service_router.my_chat_member.filter(F.chat.type == "private")


@service_router.message(
    lambda msg: any(
        [
            msg.new_chat_members,
            msg.left_chat_member,
            msg.new_chat_title,
            msg.new_chat_photo,
            msg.delete_chat_photo,
            msg.group_chat_created,
            msg.supergroup_chat_created,
            msg.channel_chat_created,
            msg.migrate_to_chat_id,
            msg.migrate_from_chat_id,
            msg.pinned_message,
        ]
    )
)
async def service_message(message: Message, bot: Bot, db: Database):
    try:
        if await db.get_setting(message.chat.id, "clean_service_msg"):
            await message.delete()
    except Exception:
        await error_report(message, bot, "service_msg", format_exc())


@service_router.chat_member(
    ChatMemberUpdatedFilter(member_status_changed=IS_NOT_MEMBER >> IS_MEMBER),
    FuncEnabled("send_welcome_msg"),
)
async def service_new_member(event: ChatMemberUpdated, db: Database):
    user = event.new_chat_member.user
    chat = event.chat

    # Только разрешённые переменные
    allowed = {
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "full_name": user.full_name or "",
    }

    text = await db.get_setting(chat.id, "welcome_message")

    try:
        text = text.format_map(allowed)
    except KeyError:
        pass  # Неизвестные ключи остаются как есть, без падения

    await event.bot.send_message(chat.id, text)

@service_router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=KICKED)
)
async def user_blocked_bot(event: ChatMemberUpdated, db: Database):
    await db.delete_active_user(event.from_user.id)


@service_router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=MEMBER)
)
async def user_unblocked_bot(event: ChatMemberUpdated, db: Database):
    await db.add_active_user(event.from_user.id)
