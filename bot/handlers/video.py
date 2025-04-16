import asyncio
import uuid
from pathlib import Path
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile

video_router = Router()
CACHE_DIR = Path(__file__).resolve().parent.parent / 'cache'

async def download_video(url: str) -> dict:
    random_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = CACHE_DIR / random_filename

    process = await asyncio.create_subprocess_exec(
        'yt-dlp', '-f "bestvideo[height<=540]+bestaudio/best[height<=540]"' '-o', str(output_path), url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0 and output_path.exists():
        return {"status": "success", "output": stdout.decode(), "file_path": str(output_path)}
    else:
        return {"status": "error", "message": stderr.decode()}
    
@video_router.message(Command("video"))
async def cmd_video(message: Message, url=None):
    split_text = message.text.split()
    processing_msg = await message.answer("⏳ Скачиваю, ждите")

    if url is None and len(split_text) > 1 and split_text[1]:
        url = split_text[1]

    if url is not None:
        result = await download_video(url)
        if result["status"] == "success":
            file = result["file_path"]
            vid = FSInputFile(file)
            await message.reply_video(vid)

            process = await asyncio.create_subprocess_exec('rm', '-f', file)
            await process.wait()
        else:
            await message.reply("❌ Не удалось загрузить видео")
    else:
        await message.reply("❌ Непредвиденная ошибка.")

    await processing_msg.delete()