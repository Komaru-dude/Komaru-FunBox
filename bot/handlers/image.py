import asyncio
from pathlib import Path
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from bot.utils.image_tools import replace_green_screen

image_router = Router()
CACHE_DIR = Path(__file__).resolve().parent.parent / 'cache'

async def get_last_profile_photo(user_id, bot):
    profile_photos = await bot.get_user_profile_photos(user_id)
    
    if not profile_photos or profile_photos.total_count == 0:
        return None

    last_photo_set = profile_photos.photos[0]
    return last_photo_set[-1]

@image_router.message(Command("lick"))
async def cmd_lick(message: Message, bot: Bot):
    user_id = message.reply_to_message.from_user.id if message.reply_to_message else message.from_user.id

    if not (profile_photo := await get_last_profile_photo(user_id, bot)):
        await message.reply("❌ У пользователя нет фото профиля!")
        return

    # Пути к файлам
    media_dir = Path(__file__).resolve().parent.parent / 'media'
    template_path = media_dir / 'lickbg.jpg'

    try:
        file = await bot.get_file(profile_photo.file_id)
        user_photo_path = CACHE_DIR / f'user_{user_id}_photo.jpg'
        await bot.download_file(file.file_path, destination=user_photo_path)
        
        # Обрабатываем изображение
        output_path = CACHE_DIR / f'lick_result_{user_id}.jpg'
        await asyncio.to_thread(
            replace_green_screen,
            template_path=str(template_path),
            new_bg_path=str(user_photo_path),
            output_path=str(output_path)
        )

        # Отправляем результат
        await message.answer_photo(FSInputFile(output_path))
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")
    finally:
        user_photo_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)