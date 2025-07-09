import asyncio
import uuid
import traceback
import shutil
import json
from pathlib import Path
from urllib.parse import quote_plus, unquote_plus
from datetime import timedelta
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    URLInputFile,
)
from bot import logger
from bot.filters.cooldown_filter import CooldownFilter
from bot.database import Database
from bot.utils.aio_tools import error_report, convert_seconds
from bot.utils.global_storage import CACHE_DIR

video_router = Router()


async def get_video_info(url: str) -> dict:
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-j",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        return {"status": "error", "message": stderr.decode()}

    try:
        info = json.loads(stdout.decode())
        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "webpage_url": info.get("webpage_url"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def download_video(
    url: str, format_code="worst/worstvideo+worstaudio/best", ext="mp4"
) -> dict:
    random_filename = f"{uuid.uuid4().hex}.{ext}"
    output_path = CACHE_DIR / random_filename

    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f",
        format_code,
        "-o",
        str(output_path),
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0 and output_path.exists():
        return {
            "status": "success",
            "output": stdout.decode(),
            "file_path": str(output_path),
        }
    else:
        return {"status": "error", "message": stderr.decode()}


@video_router.message(Command("video"), CooldownFilter("video", 150))
async def cmd_video(message: Message, bot: Bot, db: Database, url=None):
    try:
        if await db.is_user_mediabanned(message.from_user.id):
            return await message.reply(
                "❌ Вы заблокированы, это действие вам запрещено"
            )

        split_text = message.text.split()
        if not url:
            if len(split_text) > 1:
                url = split_text[1]
            else:
                return await message.reply("❌ Укажите URL видео")

        if not url.startswith("https://"):
            await message.reply("Некорректный URL")
            return

        info = await get_video_info(url)
        if info["status"] != "success":
            return await message.reply("⚠️ Не удалось получить информацию о видео.")

        safe_url = quote_plus(url)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        "🎞 Видео с аудио", callback_data=f"video:full:{safe_url}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📹 Только видео", callback_data=f"video:video:{safe_url}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔊 Только аудио", callback_data=f"video:audio:{safe_url}"
                    )
                ],
            ]
        )

        duration = info.get("duration")
        if duration:
            days, hours, minutes, seconds = convert_seconds(duration)
            parts = []
            if days > 0:
                parts.append(f"{days}д")
            if hours > 0:
                parts.append(f"{hours}ч")
            if minutes > 0:
                parts.append(f"{minutes}м")
            parts.append(f"{seconds}с")
            duration_str = " ".join(parts)
        else:
            duration_str = "неизвестно"

        caption = f"📹 <b>{info.get('title', 'Без названия')}</b>\n⏱️ Длительность: <code>{duration_str}</code>"

        await message.answer_photo(
            photo=URLInputFile(info.get("thumbnail")),
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception:
        await error_report(message, bot, "video", traceback.format_exc())


@video_router.callback_query(lambda c: c.data.startswith("video:"))
async def process_video_choice(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    command = "video"
    file_path = None
    processing_msg = None

    try:
        _, mode, raw_url = callback.data.split(":", 2)
        url = unquote_plus(raw_url)

        if mode == "audio":
            format_code = "bestaudio"
            ext = "m4a"
        elif mode == "video":
            format_code = "worstvideo"
            ext = "mp4"
        else:
            format_code = "worst/worstvideo+worstaudio/best"
            ext = "mp4"

        processing_msg = await callback.message.answer("⏳ Скачиваю, подождите...")

        result = await download_video(url, format_code=format_code, ext=ext)
        if result["status"] != "success":
            await error_report(callback.message, bot, command, result["message"])
            return

        file_path = result["file_path"]
        file = FSInputFile(file_path)

        if mode == "audio":
            await callback.message.answer_audio(file, caption="🔊 Вот ваш аудиофайл:")
        else:
            await callback.message.answer_video(file, caption="📹 Вот ваше видео:")

    except Exception:
        await error_report(callback.message, bot, command, traceback.format_exc())

    finally:
        if file_path and Path(file_path).exists():
            proc = await asyncio.create_subprocess_exec("rm", "-f", file_path)
            await proc.wait()
        if processing_msg:
            await processing_msg.delete()


@video_router.message(Command("gif"), CooldownFilter("gif", 300))
async def cmd_gif(message: Message, bot: Bot, db: Database):
    command = "gif"
    input_path = None
    frames_dir = None
    output_path = None
    processing_msg = None

    try:
        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        video = None
        if message.video:
            video = message.video
        elif message.reply_to_message and message.reply_to_message.video:
            video = message.reply_to_message.video

        if not video:
            return await message.reply(
                "❌ Отправьте видео или ответьте на видео для конвертации в GIF"
            )

        processing_msg = await message.reply("🔄 Обработка...")

        file_id = video.file_id
        file = await bot.get_file(file_id)

        input_path = CACHE_DIR / f"{file_id}.mp4"
        frames_dir = CACHE_DIR / f"{file_id}_frames"
        output_path = CACHE_DIR / f"{file_id}.gif"

        await bot.download_file(file.file_path, destination=input_path)
        frames_dir.mkdir(parents=True, exist_ok=True)

        frames_pattern = frames_dir / "frame_%04d.png"
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i",
            str(input_path),
            "-vf",
            "fps=24,scale=-1:480",
            str(frames_pattern),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()

        if process.returncode != 0:
            raise RuntimeError("Ошибка ffmpeg при извлечении кадров")

        gifski_process = await asyncio.create_subprocess_exec(
            "gifski",
            "--quality",
            "80",
            "-o",
            str(output_path),
            *sorted(frames_dir.glob("frame_*.png"), key=lambda p: p.name),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await gifski_process.communicate()

        if gifski_process.returncode != 0:
            raise RuntimeError("Ошибка gifski при создании GIF")

        if output_path.exists():
            gif = FSInputFile(output_path)
            if message.reply_to_message:
                await message.reply_to_message.reply_animation(gif)
            else:
                await message.reply_animation(gif)
        else:
            await message.reply("❌ Ошибка при конвертации.")

    except Exception:
        await error_report(message, bot, command, traceback.format_exc())

    finally:
        try:
            if input_path and input_path.exists():
                input_path.unlink(missing_ok=True)
            if frames_dir and frames_dir.exists():
                shutil.rmtree(frames_dir)
            if output_path and output_path.exists():
                output_path.unlink(missing_ok=True)
        except Exception as cleanup_error:
            logger.warning(f"Ошибка при очистке: {cleanup_error}")

        if processing_msg:
            await processing_msg.delete()
