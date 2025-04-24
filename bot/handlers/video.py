import asyncio
import uuid
import os
from pathlib import Path
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from bot import db
from bot.utils.aio_tools import error_report

video_router = Router()
CACHE_DIR = Path(__file__).resolve().parent.parent / 'cache'

async def download_video(url: str) -> dict:
    random_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = CACHE_DIR / random_filename

    process = await asyncio.create_subprocess_exec(
        'yt-dlp', '-f', 'worst/worstvideo+worstaudio/best', '-o', str(output_path), url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0 and output_path.exists():
        return {"status": "success", "output": stdout.decode(), "file_path": str(output_path)}
    else:
        return {"status": "error", "message": stderr.decode()}
    
@video_router.message(Command("video"))
async def cmd_video(message: Message, bot: Bot, url=None):
    split_text = message.text.split()
    processing_msg = await message.answer("⏳ Скачиваю, ждите")

    if url is None and len(split_text) > 1 and split_text[1]:
        url = split_text[1]

    if url is not None:
        result = await download_video(url)
        if result["status"] == "success":
            file = result["file_path"]
            vid = FSInputFile(file)
            await message.reply_video(vid, caption="📹 Вот ваше видео:")

            process = await asyncio.create_subprocess_exec('rm', '-f', file)
            await process.wait()
        else:
            report_id = uuid.uuid4()
            await message.reply(f"❌ Не удалось загрузить видео\nReport id: {report_id}")
            await bot.send_message(os.getenv("OWNER_ID"), f"Report id: {report_id}\n\nMessage: {message.text}\n\nLogs: {result["message"]}")
    else:
        await message.reply("❌ Непредвиденная ошибка.")

    await processing_msg.delete()

@video_router.message(Command("gif"))
async def cmd_gif(message: Message, bot: Bot):
    command = "gif"
    input_path = output_path = None
    try:
        if db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        video = message.video or (message.reply_to_message.video if message.reply_to_message else None)
        if not video:
            return await message.reply("❌ Отправьте видео или ответьте на видео для конвертации в GIF")

        file_id = video.file_id
        file = await message.bot.get_file(file_id)

        input_path = CACHE_DIR / f"{file_id}.mp4"
        output_path = CACHE_DIR / f"{file_id}.gif"

        await message.bot.download_file(file.file_path, destination=input_path)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", "fps=24,scale=480:-1:flags=lanczos",
            "-loop", "0", str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.communicate()

        if output_path.exists():
            gif = FSInputFile(output_path)
            if message.reply_to_message:
                await message.reply_to_message.reply_animation(gif)
            else:
                await message.reply_animation(gif)
        else:
            await message.reply("❌ Ошибка при конвертации.")
    except Exception as e:
        await error_report(message, bot, command, e)
    finally:
        if input_path and input_path.exists():
            input_path.unlink(missing_ok=True)
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)