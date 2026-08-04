import re
import time
from typing import Optional

from aiogram.enums import ChatType
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InputRichMessage, Message, ReplyParameters

from bot import logger

DRAFT_INTERVAL = 0.5  # мин. пауза между обновлениями драфта в личке
EDIT_INTERVAL = 3.0  # мин. пауза между edit_text в группах
MAX_LEN = 4096


def _thread_id(message: Message) -> Optional[int]:
    return message.message_thread_id if message.is_topic_message else None


def md_paragraphs(text: str) -> str:
    """В markdown одиночный \\n склеивает строки в один абзац — разбиваем на абзацы.

    Применять только к служебной шапке, не к ответу модели: текстовая замена
    внутри код-блоков сломала бы их.
    """
    return re.sub(r"(?<!\n)\n(?!\n)", "\n\n", text)


async def _send_plain(message: Message, text: str, base_msg: Optional[Message]) -> None:
    """Старый способ доставки: первый чанк в base_msg, остальные новыми сообщениями."""
    chunks = [text[i : i + MAX_LEN] for i in range(0, len(text), MAX_LEN)] or [""]
    for idx, chunk in enumerate(chunks):
        if idx == 0 and base_msg is not None:
            await base_msg.edit_text(chunk)
        else:
            await message.answer(chunk)


async def send_rich_reply(
    message: Message, markdown: str, base_msg: Optional[Message] = None
) -> None:
    """Отправляет финальный ответ rich-сообщением; при неудаче — плоским текстом.

    base_msg (сообщение «Обработка...») удаляется только после успешной
    отправки rich-ответа, при фолбэке используется под первый чанк.
    """
    assert message.bot is not None
    try:
        await message.bot.send_rich_message(
            chat_id=message.chat.id,
            rich_message=InputRichMessage(markdown=markdown),
            reply_parameters=ReplyParameters(
                message_id=message.message_id, allow_sending_without_reply=True
            ),
            disable_notification=True,
        )
    except Exception as e:
        logger.debug(f"sendRichMessage не удался ({e}) — отправляю плоским текстом")
        await _send_plain(message, markdown, base_msg)
        return

    if base_msg is not None:
        try:
            await base_msg.delete()
        except Exception:
            pass


class AIStreamer:
    """Стример ответа ИИ: драфты в личке, edit_text в группах, rich-финал."""

    def __init__(self, message: Message, base_msg: Message):
        assert message.bot is not None
        self.message = message
        self.base_msg = base_msg
        self.bot = message.bot
        self.is_private = message.chat.type == ChatType.PRIVATE
        # Один draft_id на весь ответ: обновления с тем же id анимируются
        self.draft_id = message.message_id
        self._next_update = 0.0
        self._rich_drafts_ok = True

    async def update(self, header: str, partial: str) -> None:
        """Промежуточное обновление во время генерации. Ошибки не роняют стрим."""
        if not partial:
            return
        now = time.monotonic()
        if now < self._next_update:
            return
        self._next_update = now + (DRAFT_INTERVAL if self.is_private else EDIT_INTERVAL)
        try:
            if self.is_private:
                await self._send_draft(f"{md_paragraphs(header)}\n\n{partial}")
            else:
                # edit_text — плоский текст, одиночные переносы работают как есть
                await self.base_msg.edit_text(f"{header}\n{partial}"[:MAX_LEN])
        except TelegramRetryAfter as e:
            self._next_update = now + e.retry_after
        except Exception:
            pass

    async def _send_draft(self, body: str) -> None:
        # Драфт — превью на 30 секунд, лимит 4096: показываем хвост текста
        tail = body[-MAX_LEN:]
        if self._rich_drafts_ok:
            try:
                await self.bot.send_rich_message_draft(
                    chat_id=self.message.chat.id,
                    draft_id=self.draft_id,
                    rich_message=InputRichMessage(markdown=tail),
                    message_thread_id=_thread_id(self.message),
                )
                return
            except TelegramRetryAfter:
                raise
            except Exception:
                # Недописанный markdown мог не распарситься — до конца этого
                # ответа стримим плоскими драфтами
                self._rich_drafts_ok = False
        await self.bot.send_message_draft(
            chat_id=self.message.chat.id,
            draft_id=self.draft_id,
            text=tail,
            message_thread_id=_thread_id(self.message),
        )

    async def finalize(self, header: str, final_markdown: str) -> None:
        """Отправляет полный ответ rich-сообщением и убирает base_msg."""
        await send_rich_reply(
            self.message, f"{md_paragraphs(header)}\n\n{final_markdown}", self.base_msg
        )
