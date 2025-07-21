import asyncio
import shutil
import traceback
import uuid
from pathlib import Path

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message

from bot import logger
from bot.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import CACHE_DIR

video_router = Router()


async def download_video(url: str) -> dict:
    random_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = CACHE_DIR / random_filename

    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f",
        "worst/worstvideo+worstaudio/best",
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
async def cmd_video(message: Message, bot: Bot, url=None):
    command = "video"
    file_path = None
    processing_msg = None

    try:

        split_text = message.text.split()
        if not url:
            if len(split_text) > 1 and split_text[1]:
                url = split_text[1]
            else:
                return await message.reply("❌ Укажите URL видео в команде")

        processing_msg = await message.answer("⏳ Скачиваю, ждите")

        result = await download_video(url)
        if result["status"] != "success":
            await error_report(message, bot, command, result["message"])
            return

        file_path = result["file_path"]
        vid = FSInputFile(file_path)
        await message.reply_video(vid, caption="📹 Вот ваше видео:")

    except Exception:
        error_traceback = traceback.format_exc()
        await error_report(message, bot, command, error_traceback)

    finally:
        if file_path and Path(file_path).exists():
            process = await asyncio.create_subprocess_exec("rm", "-f", file_path)
            await process.wait()
        if processing_msg:
            await processing_msg.delete()


@video_router.message(Command("gif"), CooldownFilter("gif", 300))
async def cmd_gif(message: Message, bot: Bot):
    command = "gif"
    input_path = None
    frames_dir = None
    output_path = None
    processing_msg = None

    try:

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
