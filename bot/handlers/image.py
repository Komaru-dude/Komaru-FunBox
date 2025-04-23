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

    last_photo_set = profile_photos.photos[0]

    largest_photo = last_photo_set[-1]
    
    return largest_photo

def replace_green_screen(template_path, new_bg_path, output_path): # Всё так же ужасно
    template = cv2.imread(template_path)
    new_bg = cv2.imread(new_bg_path)

    # 1. Препроцессинг изображения
    blurred = cv2.GaussianBlur(template, (5,5), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    # 2. Настройки для конкретных цветов
    lower_green = np.array([25, 40, 40])
    upper_green = np.array([45, 255, 255])

    # 3. Создание маски с адаптивным порогом
    mask = cv2.inRange(hsv, lower_green, upper_green)
    
    # 4. Улучшенная постобработка маски
    kernel = np.ones((5,5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    # 5. Поиск главного контура с проверкой
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("❌ Зелёная область не найдена")

    main_contour = max(contours, key=cv2.contourArea)
    x,y,w,h = cv2.boundingRect(main_contour)

    # 6. Верификация области замены
    roi_mask = mask[y:y+h, x:x+w]
    green_coverage = np.count_nonzero(roi_mask) / roi_mask.size
    if green_coverage < 0.65:  # Минимум 65% зелёного в области
        raise ValueError(f"⚠️ Плохая маска: {green_coverage*100:.1f}% заполнения")

    # 7. Точное наложение фона
    resized_bg = cv2.resize(new_bg, (w, h))
    result = template.copy()
    
    # Создаём составное изображение
    background = cv2.bitwise_and(resized_bg, resized_bg, mask=roi_mask)
    foreground = cv2.bitwise_and(template[y:y+h, x:x+w], 
                               template[y:y+h, x:x+w], 
                               mask=cv2.bitwise_not(roi_mask))
    
    result[y:y+h, x:x+w] = cv2.add(foreground, background)
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


