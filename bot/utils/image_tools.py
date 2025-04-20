import cv2
import numpy as np

def replace_green_screen(template_path, new_bg_path, output_path):
    # Загрузка шаблона с зелёным фоном и нового фона
    template = cv2.imread(template_path)
    new_bg = cv2.imread(new_bg_path)

    hsv = cv2.cvtColor(template, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 50, 50])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)

    new_bg = cv2.resize(new_bg, (template.shape[1], template.shape[0]))

    # Замена фона: где маска зелёная - берём пиксели из нового фона
    result = template.copy()
    result[mask != 0] = new_bg[mask != 0]

    cv2.imwrite(output_path, result)