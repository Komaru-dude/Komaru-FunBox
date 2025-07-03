import asyncio
import traceback
from pathlib import Path
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report
from bot.database import Database

image_router = Router()
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


async def get_last_profile_photo(user_id, bot):
    profile_photos = await bot.get_user_profile_photos(user_id)

    if not profile_photos or profile_photos.total_count == 0:
        return None

    last_photo_set = profile_photos.photos[0]
    return last_photo_set[-1]


@image_router.message(Command("jpeg"), CooldownFilter("jpeg", 150))
async def cmd_jpeg(message: Message, bot: Bot, db: Database):
    command = "jpeg"
    input_path = output_path = processing_msg = image = None
    try:
        if await db.is_user_mediabanned(message.from_user.id):
            await message.reply("❌ Вы заблокированы, это действие вам запрещено")
            return

        if message.photo:
            image = message.photo[-1]
        elif message.reply_to_message and message.reply_to_message.photo:
            image = message.reply_to_message.photo[-1]
        if not image:
            return await message.reply(
                "❌ Отправьте фото или ответьте на фото для шакализации"
            )

        processing_msg = await message.reply("🔄 Обработка...")

        file_id = image.file_id
        file = await message.bot.get_file(file_id)

        input_path = CACHE_DIR / f"{file_id}.jpg"
        output_path = CACHE_DIR / f"{file_id}-jpeged.jpg"

        await message.bot.download_file(file.file_path, destination=input_path)

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            "scale=50:-1:flags=neighbor,"
            "scale=1920:-1:flags=neighbor,"
            "noise=alls=20:allf=t+u,"
            "curves=r='0/0 0.4/0.7 1/1':"
            "g='0/0 0.4/0.7 1/1':"
            "b='0/0 0.4/0.7 1/1'",
            "-qscale:v",
            "1",
            str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()

        if output_path.exists():
            photo = FSInputFile(output_path)
            if message.reply_to_message:
                await message.reply_to_message.reply_photo(photo)
            else:
                await message.reply_photo(photo)
        else:
            await message.reply("❌ Ошибка при конвертации.")
    except Exception:
        er_traceback = traceback.format_exc()
        await error_report(message, bot, command, er_traceback)
    finally:
        if input_path and input_path.exists():
            input_path.unlink(missing_ok=True)
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)
        if processing_msg:
            await processing_msg.delete()
