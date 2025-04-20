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

    # 1. Создаём маску зелёного экрана
    hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # 2. Находим ограничивающий прямоугольник области замены
    x, y, w, h = cv2.boundingRect(mask)

    # 3. Вычисляем масштаб, чтобы фон покрыл весь прямоугольник без искажений
    bg_h, bg_w = new_bg.shape[:2]
    scale = max(w / bg_w, h / bg_h)
    resized = cv2.resize(new_bg, (int(bg_w * scale), int(bg_h * scale)))

    # 4. Обрезаем центральную часть под размер прямоугольника
    start_x = (resized.shape[1] - w) // 2
    start_y = (resized.shape[0] - h) // 2
    cropped_bg = resized[start_y:start_y + h, start_x:start_x + w]

    # 5. Вставляем «поджатый» фон в область маски
    result = template.copy()
    full_bg = np.zeros_like(template)
    full_bg[y:y + h, x:x + w] = cropped_bg
    result[mask != 0] = full_bg[mask != 0]

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
    template_path = media_dir / 'lickbg.jpg'  # Основное изображение с зелёным фоном
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


