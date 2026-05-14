"""
aruco_measure.py
================
Модуль измерения габаритов объектов по 2D-изображениям с использованием ArUco-маркера
и монокулярной оценки глубины (RTS-Mono / Depth Anything V2).

Особенности реализации:
1. Автоматическая сегментация объекта по карте глубины (без ручного выделения ROI).
2. Субпиксельная точность детекции маркера для минимизации ошибки масштаба.
3. Улучшенная визуализация карты глубины с локальной нормализацией и гамма-коррекцией.
4. Поддержка Viridis колормэпа для лучшей читаемости перепадов глубины.
"""

import argparse
import logging
from typing import Optional, Tuple, Dict

import cv2
import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────────────────────────────────────

ARUCO_DICTS = [
    ("4X4_50",   cv2.aruco.DICT_4X4_50),
    ("4X4_100",  cv2.aruco.DICT_4X4_100),
    ("4X4_250",  cv2.aruco.DICT_4X4_250),
    ("5X5_50",   cv2.aruco.DICT_5X5_50),
    ("5X5_100",  cv2.aruco.DICT_5X5_100),
    ("6X6_50",   cv2.aruco.DICT_6X6_50),
    ("6X6_100",  cv2.aruco.DICT_6X6_100),
    ("ORIGINAL", cv2.aruco.DICT_ARUCO_ORIGINAL),
]

FONT = cv2.FONT_HERSHEY_SIMPLEX
COLOR_MRK = (0, 255, 0)    # маркёр — зелёный
COLOR_OBJ = (255, 100, 0)  # объект — синий/оранжевый
COLOR_TXT = (255, 255, 255)
COLOR_BG = (30, 30, 30)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Детекция ArUco с субпиксельной точностью
# ─────────────────────────────────────────────────────────────────────────────

def detect_aruco(
    image_bgr: np.ndarray,
    target_dict: Optional[str] = None,
) -> Tuple[Optional[np.ndarray], Optional[int], Optional[str]]:
    """
    Ищет ArUco-маркёр в изображении с субпиксельным уточнением углов.

    Returns:
        corners: (4, 2) float32 — углы маркёра в пикселях, или None
        marker_id: int
        dict_name: str — имя словаря, в котором нашли
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    dicts_to_try = ARUCO_DICTS
    if target_dict:
        dicts_to_try = [(n, d)
                        for n, d in ARUCO_DICTS if target_dict.upper() in n]

    for name, dict_id in dicts_to_try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners_list, ids, _ = detector.detectMarkers(gray)

        if ids is not None and len(ids) > 0:
            # Субпиксельное уточнение углов (точность ~0.1 px)
            criteria = (cv2.TERM_CRITERIA_EPS +
                        cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(
                gray,
                corners_list[0][0].astype(np.float32),
                (11, 11),
                (-1, -1),
                criteria
            )
            marker_id = int(ids[0][0])
            logger.info(f"ArUco найден: словарь={name}, ID={marker_id}")
            return corners, marker_id, name

    logger.warning("ArUco-маркёр не найден ни в одном словаре.")
    return None, None, None


def marker_side_px(corners: np.ndarray) -> float:
    """Средняя длина стороны маркёра в пикселях."""
    sides = [np.linalg.norm(corners[i] - corners[(i + 1) % 4])
             for i in range(4)]
    return float(np.mean(sides))


def marker_center(corners: np.ndarray) -> Tuple[float, float]:
    """Центр маркёра в пикселях."""
    return float(corners[:, 0].mean()), float(corners[:, 1].mean())


# ─────────────────────────────────────────────────────────────────────────────
# 2. Масштаб и измерение
# ─────────────────────────────────────────────────────────────────────────────

class ScaleEstimator:
    """
    Вычисляет px/m масштаб на основе ArUco-маркёра известного размера.
    """

    def __init__(
        self,
        corners: np.ndarray,
        marker_size_m: float,
        depth_map: Optional[np.ndarray] = None,
        same_plane: bool = True,  # Флаг: объект и маркёр на одном столе
    ):
        self.corners = corners
        self.marker_size_m = marker_size_m
        self.depth_map = depth_map
        self.same_plane = same_plane

        self._side_px = marker_side_px(corners)
        self._cx, self._cy = marker_center(corners)

        # Глубина до маркёра (м)
        if depth_map is not None:
            h, w = depth_map.shape
            cx_i, cy_i = int(np.clip(self._cx, 0, w - 1)
                             ), int(np.clip(self._cy, 0, h - 1))
            patch = 11
            y0 = max(0, cy_i - patch // 2)
            y1 = min(h, cy_i + patch // 2 + 1)
            x0 = max(0, cx_i - patch // 2)
            x1 = min(w, cx_i + patch // 2 + 1)
            self.marker_depth_m = float(np.median(depth_map[y0:y1, x0:x1]))
        else:
            self.marker_depth_m = None

        # px/m у маркёра
        self.px_per_m_at_marker = self._side_px / marker_size_m

        logger.info(
            f"Масштаб: {self._side_px:.2f} px / {marker_size_m*1000:.1f} mm "
            f"= {self.px_per_m_at_marker:.1f} px/m"
        )

    def px_per_m_at_depth(self, depth_m: float) -> float:
        """
        Пересчёт px/m для объекта на другой глубине.
        Если same_plane=True, коррекция отключена (безопаснее для стола).
        """
        if self.same_plane or self.marker_depth_m is None or self.marker_depth_m < 0.01:
            return self.px_per_m_at_marker

        # Безопасная коррекция: ограничиваем влияние шумной глубины ±10%
        ratio = self.marker_depth_m / depth_m
        ratio = np.clip(ratio, 0.90, 1.10)
        return self.px_per_m_at_marker * ratio

    def measure_bbox(
        self,
        x1: int, y1: int, x2: int, y2: int,
    ) -> Dict[str, float]:
        """
        Измеряет bbox объекта в метрах.
        """
        w_px = abs(x2 - x1)
        h_px = abs(y2 - y1)

        if self.depth_map is not None:
            H, W = self.depth_map.shape
            rx0, ry0 = int(np.clip(x1, 0, W-1)), int(np.clip(y1, 0, H-1))
            rx1, ry1 = int(np.clip(x2, 0, W-1)), int(np.clip(y2, 0, H-1))
            roi = self.depth_map[ry0:ry1, rx0:rx1]
            # Используем медиану для устойчивости к шуму
            obj_depth_m = float(np.percentile(
                roi, 10)) if roi.size > 0 else self.marker_depth_m
            ppm = self.px_per_m_at_depth(obj_depth_m)
        else:
            obj_depth_m = None
            ppm = self.px_per_m_at_marker

        result = {
            "width_m":   w_px / ppm,
            "height_m":  h_px / ppm,
            "width_px":  w_px,
            "height_px": h_px,
            "ppm":       ppm,
        }
        if obj_depth_m is not None:
            result["depth_m"] = obj_depth_m

        return result


def measure_bbox_rotated(
    image: np.ndarray,
    bbox: Tuple[int, int, int, int],
    scale: 'ScaleEstimator'
) -> Dict[str, float]:
    """
    Измеряет объект с учётом поворота через minAreaRect.
    Корректно определяет ширину (по оси X) и высоту (по оси Y).
    """
    x1, y1, x2, y2 = bbox
    roi = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

    # Ищем контуры в ROI
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return scale.measure_bbox(x1, y1, x2, y2)  # фоллбэк на старый метод

    # Берём самый крупный контур
    c = max(contours, key=cv2.contourArea)

    # minAreaRect возвращает ((cx, cy), (width, height), angle)
    rect = cv2.minAreaRect(c)
    (center), (size_width, size_height), angle = rect

    # minAreaRect может вернуть размеры в любом порядке.
    # Нам нужно явно определить какой размер соответствует оси X (ширина),
    # а какой оси Y (высота) изображения.

    # Получаем 4 угла прямоугольника
    box = cv2.boxPoints(rect)
    box = np.int0(box)  # конвертируем в целые числа

    # Находим минимальные и максимальные координаты по X и Y
    min_x = np.min(box[:, 0])
    max_x = np.max(box[:, 0])
    min_y = np.min(box[:, 1])
    max_y = np.max(box[:, 1])

    # Вычисляем ширину и высоту в пикселях относительно изображения
    w_px = max_x - min_x
    h_px = max_y - min_y

    # Пересчёт в метры через масштаб
    ppm = scale.px_per_m_at_marker
    width_m = w_px / ppm
    height_m = h_px / ppm

    # Глубину берём как медиану в ROI (как в старом методе)
    depth_m = None
    if scale.depth_map is not None:
        H, W = scale.depth_map.shape
        rx0, ry0 = int(np.clip(x1, 0, W-1)), int(np.clip(y1, 0, H-1))
        rx1, ry1 = int(np.clip(x2, 0, W-1)), int(np.clip(y2, 0, H-1))
        roi_depth = scale.depth_map[ry0:ry1, rx0:rx1]
        depth_m = float(np.percentile(roi_depth, 10)
                        ) if roi_depth.size > 0 else None

    return {
        "width_m": width_m,      # Размер по оси X изображения
        "height_m": height_m,    # Размер по оси Y изображения
        "width_px": w_px,
        "height_px": h_px,
        "depth_m": depth_m,
        "ppm": ppm,
        "rotated": True,
        "angle": angle  # Можно сохранить угол для отладки
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Автоматическая сегментация объекта по глубине
# ─────────────────────────────────────────────────────────────────────────────

def segment_object_from_depth(
    depth_map: np.ndarray,
    image_bgr: np.ndarray,
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
    min_object_area_ratio: float = 0.05,  # Минимум 5% от кадра
) -> Optional[Tuple[Tuple[int, int, int, int], np.ndarray]]:
    """
    Автоматически сегментирует объект из карты глубины.

    Args:
        depth_map: карта глубины (H, W) в метрах
        image_bgr: исходное изображение для маскирования фона
        marker_bbox: bbox маркера (исключается из анализа)
        min_object_area_ratio: минимальная доля площади объекта

    Returns:
        (bbox, mask) или None если не удалось сегментировать
    """
    H, W = depth_map.shape

    # 1. Создаём рабочую копию глубины, исключая маркер
    depth_work = depth_map.copy()
    if marker_bbox:
        x1, y1, x2, y2 = marker_bbox
        # Исключаем область маркера, чтобы он не влиял на пороги
        depth_work[y1:y2, x1:x2] = np.nan

    # 2. Маска валидных значений глубины
    valid_mask = ~np.isnan(depth_work) & (
        depth_work > 0.1) & (depth_work < 10.0)

    if valid_mask.sum() < 100:
        logger.warning("Слишком мало валидных пикселей глубины")
        return None

    # 3. Нормализуем глубину для бинаризации
    depth_valid = depth_work[valid_mask]
    depth_norm = np.zeros_like(depth_work)
    depth_norm[valid_mask] = (depth_valid - depth_valid.min()) / \
        (depth_valid.max() - depth_valid.min() + 1e-5)

    # 4. Бинаризация (Otsu или Adaptive)
    # Объект обычно ближе камеры, чем фон (если снято сверху/сбоку под углом)
    # Или наоборот, зависит от сцены. Здесь используем инверсию, т.к. ближние объекты темнее на некоторых картах
    # Но лучше использовать Otsu на нормализованной карте.
    try:
        from skimage.filters import threshold_otsu
        thresh_val = threshold_otsu(depth_norm[valid_mask])
        _, binary = cv2.threshold(
            (depth_norm * 255).astype(np.uint8),
            int(thresh_val * 255),
            255,
            # Предполагаем, что объект ближе (темнее) или дальше (светлее) - нужно проверить
            cv2.THRESH_BINARY_INV
        )
    except ImportError:
        # Fallback на простой порог если skimage нет
        _, binary = cv2.threshold(
            (depth_norm * 255).astype(np.uint8),
            127,
            255,
            cv2.THRESH_BINARY_INV
        )

    # 5. Морфология для очистки шума
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)

    # 6. Находим контуры
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        logger.warning("Контуры не найдены")
        return None

    # 7. Берём наибольший контур (это объект)
    min_area = H * W * min_object_area_ratio
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]

    if not valid_contours:
        # Если нет больших контуров, берем просто самый большой из всех, если он разумного размера
        largest_c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_c) < min_area * 0.5:
            logger.warning(
                f"Нет контуров больше {min_area} px, самый большой слишком мал")
            return None
        largest_contour = largest_c
    else:
        largest_contour = max(valid_contours, key=cv2.contourArea)

    # 8. Bbox и маска
    x, y, w, h = cv2.boundingRect(largest_contour)
    bbox = (x, y, x + w, y + h)

    # Создаём маску
    mask = np.zeros_like(binary)
    cv2.drawContours(mask, [largest_contour], -1, 255, -1)
    mask = mask.astype(bool)

    logger.info(
        f"Объект сегментирован: bbox={bbox}, площадь={cv2.contourArea(largest_contour)} px")

    return bbox, mask


# ─────────────────────────────────────────────────────────────────────────────
# 4. Визуализация (с улучшениями)
# ─────────────────────────────────────────────────────────────────────────────

def enhance_depth_visualization(
    depth_map: np.ndarray,
    bbox: Optional[Tuple[int, int, int, int]] = None,
    gamma: float = 0.75,
    colormap: int = cv2.COLORMAP_VIRIDIS
) -> np.ndarray:
    """
    Улучшает визуализацию карты глубины:
    1. Локальная нормализация по области объекта (если bbox задан)
    2. Гамма-коррекция для усиления контраста в средних тонах
    3. Применение высококонтрастного колормэпа (VIRIDIS по умолчанию)
    4. Подсветка границ объекта белым контуром
    """
    # 1. Нормализуем СТРОГО по области объекта (bbox), чтобы фон не влиял на контраст
    if bbox:
        x1, y1, x2, y2 = bbox
        H, W = depth_map.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)

        if x2 > x1 and y2 > y1:
            roi_depth = depth_map[y1:y2, x1:x2]
            p_min, p_max = np.percentile(roi_depth, (1, 99))
        else:
            p_min, p_max = np.percentile(depth_map, (1, 99))
    else:
        p_min, p_max = np.percentile(depth_map, (1, 99))

    depth_range = p_max - p_min
    if depth_range < 1e-5:
        depth_norm = np.zeros_like(depth_map)
    else:
        depth_norm = np.clip((depth_map - p_min) / (depth_range + 1e-5), 0, 1)

    # 2. Гамма-коррекция
    depth_norm = np.power(depth_norm, 1.0 / gamma)

    # 3. Применяем колормэп
    depth_u8 = (depth_norm * 255).astype(np.uint8)
    depth_vis = cv2.applyColorMap(depth_u8, colormap)

    # 4. Подсветка границ
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(depth_vis, (x1, y1), (x2, y2), (255, 255, 255), 2)

    return depth_vis


def draw_marker(image: np.ndarray, corners: np.ndarray, marker_id: int, marker_size_m: float) -> None:
    """Рисует контур маркёра и подписывает его реальный размер."""
    pts = corners.astype(int)
    cv2.polylines(image, [pts], isClosed=True, color=COLOR_MRK, thickness=2)
    for pt in pts:
        cv2.circle(image, tuple(pt), 5, COLOR_MRK, -1)

    cx, cy = marker_center(corners)
    label = f"ArUco ID={marker_id} [{marker_size_m*1000:.1f}mm]"
    _put_label(image, label, int(cx), int(corners[:, 1].min()) - 12, COLOR_MRK)


def draw_measurement(
    image: np.ndarray,
    x1: int, y1: int, x2: int, y2: int,
    measurements: Dict[str, float],
    label: str = "Объект",
) -> None:
    """Рисует bbox объекта и аннотацию с реальными размерами."""
    cv2.rectangle(image, (x1, y1), (x2, y2), COLOR_OBJ, 2)

    lines = [
        f"{label}",
        f"W: {measurements['width_m']*100:.1f} cm",
        f"H: {measurements['height_m']*100:.1f} cm",
    ]
    if "depth_m" in measurements:
        lines.append(f"Z: {measurements['depth_m']:.2f} m")

    tx = x1
    ty = y1 - 10 - (len(lines) - 1) * 22
    for line in lines:
        _put_label(image, line, tx, ty, COLOR_OBJ)
        ty += 22

    _draw_dim_arrow(image, x1, y2 + 15, x2, y2 + 15,
                    f"{measurements['width_m']*100:.1f} cm", COLOR_OBJ)
    _draw_dim_arrow(image, x2 + 15, y1, x2 + 15, y2,
                    f"{measurements['height_m']*100:.1f} cm", COLOR_OBJ, vertical=True)


def _put_label(image, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.6, 1)
    cv2.rectangle(image, (x - 2, y - th - 4),
                  (x + tw + 2, y + 4), COLOR_BG, -1)
    cv2.putText(image, text, (x, y), FONT, 0.6, color, 2, cv2.LINE_AA)


def _draw_dim_arrow(image, x1, y1, x2, y2, label, color, vertical=False):
    cv2.arrowedLine(image, (x1, y1), (x2, y2), color, 1, tipLength=0.05)
    cv2.arrowedLine(image, (x2, y2), (x1, y1), color, 1, tipLength=0.05)
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    _put_label(image, label, mx, my, color)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Публичный API (Автоматический режим)
# ─────────────────────────────────────────────────────────────────────────────

def measure_object_auto(
    image_bgr: np.ndarray,
    marker_size_m: float,
    depth_map: np.ndarray,
    aruco_dict: Optional[str] = None,
    object_label: str = "Объект",
    same_plane: bool = True,
) -> Tuple[Optional[Dict[str, float]], np.ndarray, Optional[np.ndarray]]:
    """
    Полностью автоматическое измерение:
    1. Находит маркер
    2. Сегментирует объект по глубине
    3. Вычисляет габариты

    Returns:
        measurements, annotated_image, object_mask
    """
    result_img = image_bgr.copy()

    # 1. Детекция маркера
    corners, marker_id, dict_name = detect_aruco(image_bgr, aruco_dict)
    if corners is None:
        logger.error("Маркёр не найден")
        return None, result_img, None

    marker_bbox_cv = cv2.boundingRect(corners.astype(np.float32))
    marker_bbox = tuple(marker_bbox_cv)
    draw_marker(result_img, corners, marker_id, marker_size_m)

    # 2. Масштаб
    scale = ScaleEstimator(corners, marker_size_m,
                           depth_map, same_plane=same_plane)

    # 3. Автоматическая сегментация
    seg_result = segment_object_from_depth(
        depth_map,
        image_bgr,
        marker_bbox=marker_bbox
    )

    if seg_result is None:
        logger.error("Не удалось сегментировать объект автоматически")
        return None, result_img, None

    bbox, object_mask = seg_result

    # 4. Измерение
    measurements = measure_bbox_rotated(result_img, bbox, scale)

    # 5. Визуализация
    draw_measurement(result_img, bbox[0], bbox[1],
                     bbox[2], bbox[3], measurements, object_label)

    # Рисуем маску полупрозрачно для наглядности
    mask_overlay = result_img.copy()
    mask_overlay[object_mask] = (
        mask_overlay[object_mask] * 0.7 + np.array([0, 255, 0]) * 0.3).astype(np.uint8)
    cv2.addWeighted(mask_overlay, 0.5, result_img, 0.5, 0, result_img)

    logger.info(
        f"Результат [{object_label}]: "
        f"W={measurements['width_m']*100:.1f} cm, "
        f"H={measurements['height_m']*100:.1f} cm"
    )

    return measurements, result_img, object_mask


def measure_from_wrapper(
    image_bgr: np.ndarray,
    wrapper,                       # DepthAnythingV2OpenVINO instance
    marker_size_m: float,
    multi_scale: bool = False,
    object_label: str = "Объект",
    same_plane: bool = True,
    enhance_visualization: bool = True,
    gamma: float = 0.75,
) -> Tuple[Optional[Dict[str, float]], np.ndarray, np.ndarray]:
    """
    Полностью автоматический пайплайн без ручного вмешательства.
    """
    logger.info("Запуск DA-V2 (metric depth)...")
    depth_map = wrapper.estimate(image_bgr, multi_scale=multi_scale)

    # Улучшенная визуализация с VIRIDIS
    if enhance_visualization:
        logger.info("Применение улучшенной визуализации (VIRIDIS)...")
        # Сначала получаем bbox из сегментации, чтобы нормализовать по нему
        # Но пока вызываем measure_object_auto, который вернет bbox
        # Для визуализации пока передадим None, нормализация будет глобальной,
        # либо можно вызвать сегментацию отдельно перед этим.
        # Для простоты используем глобальную нормализацию с гаммой.
        depth_vis = enhance_depth_visualization(
            depth_map,
            bbox=None,
            gamma=gamma,
            colormap=cv2.COLORMAP_VIRIDIS
        )
    else:
        depth_vis = wrapper.estimate_visual(
            image_bgr,
            normalize="metric_range",
            multi_scale=multi_scale
        )

    # Автоматическое измерение
    measurements, annotated, object_mask = measure_object_auto(
        image_bgr,
        marker_size_m=marker_size_m,
        depth_map=depth_map,
        object_label=object_label,
        same_plane=same_plane,
    )

    return measurements, annotated, depth_vis


# ─────────────────────────────────────────────────────────────────────────────
# 6. CLI (Для тестирования)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(
        description="ArUco object measurement (Auto Mode)")
    p.add_argument("--image",       required=True,
                   help="Путь к изображению")
    p.add_argument("--marker-size", type=float, default=0.055,
                   help="Физический размер стороны маркёра в метрах (default: 0.055)")
    p.add_argument("--output",      default="measurement_result.jpg")
    p.add_argument("--label",       default="Object")
    p.add_argument("--gamma",       type=float, default=0.75,
                   help="Гамма-коррекция для визуализации глубины")
    return p.parse_args()


if __name__ == "__main__":

    print("Этот модуль предназначен для импорта в основной пайплайн.")
    print("Для теста используйте отдельный скрипт test_cv.py, вызывающий measure_from_wrapper.")
