from traceback import format_exc

from aiogram import Bot, Router
from aiogram.filters.chat_member_updated import (
    IS_MEMBER,
    IS_NOT_MEMBER,
    KICKED,
    MEMBER,
    ChatMemberUpdatedFilter,
)
from aiogram.types import ChatMemberUpdated, Message

from bot import logger
from bot.database.database import Database
from bot.filters.func_filter import FuncEnabled
from bot.utils.aio_tools import error_report

service_router = Router()


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
    text = text or ""

    try:
        text = text.format_map(allowed)
    except KeyError:
        pass  # Неизвестные ключи остаются как есть, без падения

    await event.bot.send_message(chat.id, text)


@service_router.my_chat_member(
    lambda ev: (
        getattr(ev, "new_chat_member", None) is not None
        and getattr(ev.new_chat_member.user, "is_bot", False)
        and getattr(ev.new_chat_member, "status", None) == "member"
        and getattr(ev.chat, "type", None) in ("group", "supergroup")
    )
)
async def bot_added_to_group(
    event: ChatMemberUpdated, db: Database
):  # Убедитесь, что тип Database импортирован
    chat = event.chat

    logger.info(
        f"bot_added_to_group triggered for chat_id={chat.id} chat_type={getattr(chat, 'type', None)}"
    )

    # 3. Оптимизировано: f-строка очищена от лишнего условного форматирования (у групп всегда есть title)
    text = (
        f"👋 Привет! Спасибо, что добавили меня в группу «{chat.title}».\n\n"
        "▶️ Перед началом работы настоятельно рекомендуем заглянуть в статью по быстрой настройке: "
        "https://not-a-dude.github.io/Komaru-FunBox/docs/setup/faststart/\n"
        "💿 В этой же базе знаний вы найдете множество других полезных материалов, "
        "которые объяснят все тонкости работы бота."
    )

    # Ensure we have a string to send
    text = text or ""

    try:
        await event.bot.send_message(chat.id, text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка при отправке приветственного сообщения: {e}")


@service_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated, db: Database):
    await db.delete_active_user(event.from_user.id)


@service_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot(event: ChatMemberUpdated, db: Database):
    await db.add_active_user(event.from_user.id)
