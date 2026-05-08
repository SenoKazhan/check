#!/usr/bin/env python3
"""Генерирует 3 тестовых изображения с ArUco-маркерами для проверки конвейера."""
import cv2
import numpy as np
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "tests/assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def gen_image_with_aruco(filename: str, marker_id: int = 0):
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    marker = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 200)
    
    # Белый фон 640x480, маркер в центре
    img = np.ones((480, 640, 3), dtype=np.uint8) * 255
    
    # Конвертируем маркер из grayscale в BGR
    marker_colored = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    
    x, y = (640 - 200)//2, (480 - 200)//2
    img[y:y+200, x:x+200] = marker_colored
    
    cv2.imwrite(str(OUT_DIR / filename), img)
    print(f"✅ Создан: {OUT_DIR / filename}")

if __name__ == "__main__":
    gen_image_with_aruco("front_test.png", marker_id=0)
    gen_image_with_aruco("side_test.png", marker_id=1)
    gen_image_with_aruco("top_test.png", marker_id=2)
    print("📁 Готово. Файлы лежат в backend/tests/assets/")