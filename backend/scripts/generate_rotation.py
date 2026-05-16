#!/usr/bin/env python3
"""
Генерирует синтетические примеры для диплома:
- 4 сцены с объектом, повернутым на 0°, 15°, 30°, 45° относительно ArUco-маркера.
- Каждое изображение содержит разметку (красная линия) и ось объекта (зеленая).
"""
import cv2
import numpy as np
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "tests/assets/rotation_examples"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Генерируем маркер ArUco 6x6_250, ID=42
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
marker_img = cv2.aruco.generateImageMarker(aruco_dict, 42, 120)  # 120 px

ANGLES = [0, 15, 30, 45]


def draw_scene(angle_deg: int, idx: int) -> np.ndarray:
    # Белый фон 800x600
    canvas = np.ones((600, 800, 3), dtype=np.uint8) * 255

    # Вставляем маркер в левый нижний угол (имитация разметки на ленте)
    mx, my = 80, 420
    marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)
    canvas[my:my+120, mx:mx+120] = marker_bgr

    # Углы маркера для отладочной отрисовки (top-left, top-right, bottom-right, bottom-left)
    corners = np.array([
        [mx, my],
        [mx+120, my],
        [mx+120, my+120],
        [mx, my+120]
    ], dtype=np.float32)

    # Рисуем линию разметки (красная, продолжение нижней стороны маркера)
    cv2.line(canvas, (mx-40, my+120), (mx+200, my+120), (0, 0, 255), 2)

    # Рисуем объект (синий прямоугольник 300x150) в центре, повернутый на angle_deg
    cx, cy = 450, 300
    rect = ((cx, cy), (300, 150), angle_deg)
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.fillPoly(canvas, [box], (220, 100, 50))  # синий заливка
    cv2.polylines(canvas, [box], True, (180, 60, 30), 2)

    # Создаем маску объекта для вычисления оси
    mask = np.zeros((600, 800), dtype=np.uint8)
    cv2.fillPoly(mask, [box], 255)

    # Вычисляем и рисуем центральную ось (зеленая)
    m = cv2.moments(mask)
    if m["m00"] > 0:
        ocx = m["m10"] / m["m00"]
        ocy = m["m01"] / m["m00"]
        mu20, mu02, mu11 = m["mu20"], m["mu02"], m["mu11"]
        if abs(mu20 - mu02) > 1e-6:
            theta = 0.5 * np.arctan2(2 * mu11, mu20 - mu02)
        else:
            theta = np.pi / 4
        vx, vy = np.cos(theta), np.sin(theta)
        cv2.line(canvas,
                 (int(ocx - vx*160), int(ocy - vy*160)),
                 (int(ocx + vx*160), int(ocy + vy*160)),
                 (0, 255, 0), 2)

    # Подписи
    cv2.putText(canvas, f"Object rotation: {angle_deg}°", (320, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2)
    cv2.putText(canvas, "ArUco marker (ground truth axis)", (40, 400),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 1)
    cv2.putText(canvas, "Red = marking line", (40, 560),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    cv2.putText(canvas, "Green = principal axis", (40, 580),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 0), 1)

    return canvas


if __name__ == "__main__":
    for angle in ANGLES:
        img = draw_scene(angle, angle)
        fname = OUT_DIR / f"rotated_{angle:02d}deg.png"
        cv2.imwrite(str(fname), img)
        print(f"✅ Сохранено: {fname}")

    print(f"\n📁 Все примеры в: {OUT_DIR}")