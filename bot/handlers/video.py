import asyncio
import uuid
import traceback
from pathlib import Path
from asyncio import subprocess
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
async def cmd_video(message: Message, bot: Bot):
    command = "video"
    url = None
    file_path = None
    processing_msg = None

    try:
        if db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        processing_msg = await message.answer("⏳ Скачиваю, ждите")

        split_text = message.text.split()
        if len(split_text) > 1 and split_text[1]:
            url = split_text[1]
        else:
            return await message.reply("❌ Укажите URL видео в команде")

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
            process = await asyncio.create_subprocess_exec('rm', '-f', file_path)
            await process.wait()
        if processing_msg:
            await processing_msg.delete()

@video_router.message(Command("gif"))
async def cmd_gif(message: Message, bot: Bot):
    if db.is_user_mediabanned(message.from_user.id):
        return await message.reply("❌ Вы заблокированы, это действие вам запрещено")

    video = message.video or (message.reply_to_message and message.reply_to_message.video)
    if not video:
        return await message.reply("❌ Пришлите видео или ответьте на видео")

    processing = await message.reply("🔄 Обработка GIF...")
    file = await bot.get_file(video.file_id)

    inp = CACHE_DIR / f"{video.file_id}.mp4"
    pal = CACHE_DIR / f"{video.file_id}_pal.png"
    out = CACHE_DIR / f"{video.file_id}.gif"
    await bot.download_file(file.file_path, destination=inp)

    try:
        # 1. Генерация палитры
        cmd1 = [
            "ffmpeg", "-y", "-i", str(inp),
            "-vf", "fps=20,scale=480:-1:flags=lanczos,palettegen",
            str(pal)
        ]
        p1 = await asyncio.create_subprocess_exec(*cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await p1.communicate()

        # 2. Применение палитры
        cmd2 = [
            "ffmpeg", "-y", "-i", str(inp), "-i", str(pal),
            "-filter_complex", "fps=20,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=none",
            str(out)
        ]
        p2 = await asyncio.create_subprocess_exec(*cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await p2.communicate()

        if out.exists():
            gif = FSInputFile(out)
            if message.reply_to_message:
                await message.reply_to_message.reply_animation(gif)
            else:
                await message.reply_animation(gif)
        else:
            await message.reply("❌ Ошибка при конвертации.")
    finally:
        for path in (inp, pal, out):
            if path.exists():
                path.unlink()
        await processing.delete()