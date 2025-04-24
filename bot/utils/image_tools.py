import cv2
import numpy as np

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