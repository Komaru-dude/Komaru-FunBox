import cv2, asyncio, os
import numpy as np
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from pathlib import Path

image_router = Router()

async def get_last_profile_photo(user_id, bot):
    profile_photos = await bot.get_user_profile_photos(user_id)
    
    if not profile_photos or profile_photos.total_count == 0:
        return None

    last_photo_set = profile_photos.photos[-1]

    largest_photo = last_photo_set[-1]
    
    return largest_photo

def replace_green_screen(template_path, new_bg_path, output_path):
    template = cv2.imread(template_path)
    new_bg = cv2.imread(new_bg_path)

    # Создаём маску для зелёного цвета
    hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 50, 50])  # Минимальный оттенок зелёного
    upper_green = np.array([85, 255, 255])  # Максимальный оттенок зелёного
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # Подгоняем размер нового фона под шаблон
    new_bg = cv2.resize(new_bg, (template.shape[1], template.shape[0]))

    # Замена фона: где маска зелёная - берём пиксели из нового фона
    result = template.copy()
    result[mask != 0] = new_bg[mask != 0]

    # Сохраняем результат
    cv2.imwrite(output_path, result)

@image_router.message(Command("lick"))
async def cmd_lick(message: Message, bot: Bot):
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
    else:
        user_id = message.from_user.id

    profile_photo = await get_last_profile_photo(user_id, bot)
    if not profile_photo:
        await message.reply("❌ У пользователя нет фото профиля!")
        return

    # Пути к файлам
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent
    media_dir = parent_dir / 'media'
    temp_dir = parent_dir / 'temp'
    temp_dir.mkdir(exist_ok=True)

    # Скачиваем аватар пользователя
    try:
        file = await bot.get_file(profile_photo.file_id)
        user_photo_path = temp_dir / f'user_{user_id}_photo.jpg'
        await bot.download_file(file.file_path, destination=str(user_photo_path))
    except Exception as e:
        await message.reply(f"❌ Ошибка загрузки фото: {e}")
        return

    # Параметры обработки
    template_path = media_dir / 'lick.jpg'  # Основное изображение с зелёным фоном
    output_path = temp_dir / f'lick_result_{user_id}.jpg'

    try:
        await asyncio.to_thread(
            replace_green_screen,
            template_path=str(template_path),
            new_bg_path=str(user_photo_path),
            output_path=str(output_path)
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка обработки: {e}")
        return

    # Отправляем результат
    try:
        result_photo = FSInputFile(output_path)
        await message.answer_photo(result_photo)
    finally:
        user_photo_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


