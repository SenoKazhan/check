"""
aruco_measure.py
================
Модуль измерения габаритов объектов по 2D-изображениям с использованием ArUco-маркера
и монокулярной оценки глубины (Depth Anything V2).

Особенности реализации:
1. Автоматическая сегментация объекта по карте глубины (без ручного выделения ROI).
2. Субпиксельная точность детекции маркера для минимизации ошибки масштаба.
3. Выравнивание ориентации объекта относительно сетки площадки через аффинные преобразования.
   (Реализация рекомендации руководителя по обработке неидеального расположения предметов).
4. Улучшенная визуализация карты глубины с локальной нормализацией и гамма-коррекцией.
5. Поддержка Viridis колормэпа для лучшей читаемости перепадов глубины.

Архитектурное обоснование выравнивания:
--------------------------------------
В реальных условиях предметы на ленте могут быть повернуты. Для корректного сопоставления
габаритов (length, width) с осями контейнера в задаче 3D-упаковки применяется трёхэтапный
пре-процессинг:
1. Выделение контура и расчёт угла ориентации (minAreaRect).
2. Аффинный поворот изображения, маски и карты глубины к эталонной оси (0°).
3. Измерение Axis-Aligned Bounding Box (AABB) на выровненных данных.

Ссылки на разделы пояснительной записки:
- Раздел 4.2: Модуль компьютерного зрения, алгоритм выравнивания.
- Приложение Б: Схема структурная, блок «Предобработка изображений».
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Union

import cv2
import numpy as np
from numpy.typing import NDArray

# Локальные импорты проекта
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Константы модуля
# ─────────────────────────────────────────────────────────────────────────────

# Словари ArUco: (имя, константа OpenCV)
ARUCO_DICTS: List[Tuple[str, int]] = [
    ("4X4_50",   cv2.aruco.DICT_4X4_50),
    ("4X4_100",  cv2.aruco.DICT_4X4_100),
    ("4X4_250",  cv2.aruco.DICT_4X4_250),
    ("5X5_50",   cv2.aruco.DICT_5X5_50),
    ("5X5_100",  cv2.aruco.DICT_5X5_100),
    ("6X6_50",   cv2.aruco.DICT_6X6_50),
    ("6X6_100",  cv2.aruco.DICT_6X6_100),
    ("ORIGINAL", cv2.aruco.DICT_ARUCO_ORIGINAL),
]

# Параметры визуализации
FONT: int = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE: float = 0.6
FONT_THICKNESS: int = 2
LINE_TYPE: int = cv2.LINE_AA

# Цвета в формате BGR (OpenCV)
COLOR_MARKER: Tuple[int, int, int] = (0, 255, 0)      # зелёный
COLOR_OBJECT: Tuple[int, int, int] = (255, 100, 0)    # оранжевый
COLOR_TEXT: Tuple[int, int, int] = (255, 255, 255)    # белый
COLOR_BACKGROUND: Tuple[int, int, int] = (30, 30, 30)  # тёмно-серый

# Параметры сегментации
MIN_OBJECT_AREA_RATIO: float = 0.05  # Минимум 5% от кадра
MIN_VALID_PIXELS: int = 100          # Порог валидных пикселей глубины
DEPTH_MIN_M: float = 0.1             # Минимальная глубина (м)
DEPTH_MAX_M: float = 10.0            # Максимальная глубина (м)
MORPH_KERNEL_SIZE: Tuple[int, int] = (5, 5)
MORPH_OPEN_ITERATIONS: int = 2
MORPH_CLOSE_ITERATIONS: int = 3

# Параметры выравнивания
ALIGNMENT_CORRECTION_TOLERANCE: float = 0.10  # Допуск коррекции ±10%
SUBPIXEL_WIN_SIZE: Tuple[int, int] = (11, 11)
SUBPIXEL_ZERO_ZONE: Tuple[int, int] = (-1, -1)
SUBPIXEL_CRITERIA_EPS: float = 0.001
SUBPIXEL_CRITERIA_MAX_ITER: int = 30

# Параметры визуализации глубины
DEPTH_VIS_GAMMA: float = 0.75
DEPTH_VIS_COLORMAP: int = cv2.COLORMAP_VIRIDIS
DEPTH_VIS_PERCENTILE_LOW: float = 1.0
DEPTH_VIS_PERCENTILE_HIGH: float = 99.0


# ─────────────────────────────────────────────────────────────────────────────
# 1. Модуль выравнивания объекта относительно сетки площадки
# ─────────────────────────────────────────────────────────────────────────────

def align_object_to_grid(
    image_rgb: NDArray[np.uint8],
    depth_map: NDArray[np.float32],
    object_mask: NDArray[np.bool_],
    reference_angle_deg: float = 0.0,
) -> Tuple[NDArray[np.uint8], NDArray[np.float32], NDArray[np.bool_], float]:
    """
    Вычисляет угол поворота объекта и применяет аффинное преобразование
    для выравнивания его главных осей относительно эталонной сетки.

    Архитектурное назначение:
    -------------------------
    Функция реализует рекомендацию руководителя по обработке случаев
    неидеального расположения предмета на сортировочной ленте. После
    выравнивания габариты объекта, вычисленные через axis-aligned bounding box,
    корректно сопоставляются с осями контейнера в задаче трёхмерной упаковки.

    Алгоритм:
    ---------
    1. Поиск внешнего контура объекта по бинарной маске.
    2. Вычисление минимального описывающего прямоугольника (minAreaRect).
    3. Нормализация угла: OpenCV возвращает [-90, 0), приводим к [0, 180).
    4. Расчёт корректирующего угла: correction = -(detected - reference).
    5. Построение матрицы аффинного преобразования вокруг центра объекта.
    6. Применение warpAffine к изображению, маске (INTER_NEAREST) и глубине.
    7. Маскирование фона в карте глубины для исключения артефактов интерполяции.

    Метрическая целостность:
    ------------------------
    - Для маски используется интерполяция ближайшего соседа (INTER_NEAREST),
      что сохраняет чёткость границ после поворота.
    - Для карты глубины допустима линейная интерполяция (INTER_LINEAR),
      однако область вне объекта обнуляется по итоговой маске.
    - Коэффициент масштаба (px/m) вычисляется до выравнивания и применяется
      к выровненному изображению, что исключает накопление погрешности.

    Параметры:
    ----------
    image_rgb : NDArray[np.uint8]
        RGB-изображение размером (H, W, 3), тип uint8.
    depth_map : NDArray[np.float32]
        Карта глубины в метрах размером (H, W), тип float32.
    object_mask : NDArray[np.bool_]
        Бинарная маска объекта размером (H, W), тип bool.
    reference_angle_deg : float, optional
        Угол эталонной оси разметки площадки (по умолчанию 0.0 = горизонталь).

    Возвращает:
    -----------
    Tuple[NDArray[np.uint8], NDArray[np.float32], NDArray[np.bool_], float]
        - aligned_img : выровненное RGB-изображение.
        - aligned_depth : выровненная карта глубины (фон обнулён).
        - aligned_mask : выровненная бинарная маска объекта.
        - detected_angle : вычисленный угол ориентации объекта в градусах.

    Примечания:
    -----------
    - Функция детерминирована: при одинаковых входных данных возвращает
      идентичные результаты, что критично для воспроизводимости измерений.
    - При отсутствии контура возвращает исходные данные без модификации.
    - Логирование выполняется на уровне INFO для отладки и WARNING для ошибок.
    """
    # 1. Поиск контура и вычисление ориентации
    contours, _ = cv2.findContours(
        object_mask.astype(np.uint8),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        logger.warning("Контур объекта не найден для выравнивания")
        return image_rgb, depth_map, object_mask, 0.0

    # Выбираем контур максимальной площади (основной объект)
    primary_contour = max(contours, key=cv2.contourArea)
    (center_x, center_y), (width_rect,
                           height_rect), raw_angle = cv2.minAreaRect(primary_contour)

    # Нормализация угла: OpenCV возвращает [-90, 0) для minAreaRect
    # Приводим к диапазону [0, 180) с учётом возможного обмена ширины/высоты
    normalized_angle = _normalize_min_area_rect_angle(
        raw_angle, width_rect, height_rect)

    # 2. Вычисление корректирующего угла для выравнивания по эталонной оси
    correction_angle = -(normalized_angle - reference_angle_deg)
    rotation_center = (float(center_x), float(center_y))

    # 3. Построение матрицы аффинного преобразования (поворот вокруг центра)
    rotation_matrix = cv2.getRotationMatrix2D(
        rotation_center, correction_angle, scale=1.0)
    image_height, image_width = image_rgb.shape[:2]

    # 4. Применение преобразования к изображению (линейная интерполяция)
    aligned_image = cv2.warpAffine(
        image_rgb,
        rotation_matrix,
        (image_width, image_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )

    # Для маски — интерполяция ближайшего соседа для сохранения чёткости границ
    aligned_mask = cv2.warpAffine(
        object_mask.astype(np.uint8),
        rotation_matrix,
        (image_width, image_height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    ).astype(bool)

    # Для карты глубины — линейная интерполяция допустима, но фон обнуляем по маске
    aligned_depth = cv2.warpAffine(
        depth_map,
        rotation_matrix,
        (image_width, image_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0.0,
    )
    # Исключаем влияние фона на статистику глубины внутри объекта
    aligned_depth[~aligned_mask] = 0.0

    logger.info(
        "Объект выровнен: detected_angle=%.1f°, correction=%.1f°, center=(%.1f, %.1f)",
        normalized_angle,
        correction_angle,
        center_x,
        center_y,
    )
    return aligned_image, aligned_depth, aligned_mask, normalized_angle


def _normalize_min_area_rect_angle(
    raw_angle: float,
    width_rect: float,
    height_rect: float,
) -> float:
    """
    Нормализует угол minAreaRect из диапазона [-90, 0) в [0, 180).

    Параметры:
    ----------
    raw_angle : float
        Сырой угол от cv2.minAreaRect.
    width_rect : float
        Ширина прямоугольника.
    height_rect : float
        Высота прямоугольника.

    Возвращает:
    -----------
    float
        Нормализованный угол в градусах.
    """
    if width_rect < height_rect:
        return raw_angle + 90.0
    return raw_angle


# ─────────────────────────────────────────────────────────────────────────────
# 2. Детекция ArUco-маркёра с субпиксельной точностью
# ─────────────────────────────────────────────────────────────────────────────

def detect_aruco(
    image_bgr: NDArray[np.uint8],
    target_dict: Optional[str] = None,
) -> Tuple[Optional[NDArray[np.float32]], Optional[int], Optional[str]]:
    """
    Ищет ArUco-маркёр в изображении с субпиксельным уточнением углов.

    Параметры:
    ----------
    image_bgr : NDArray[np.uint8]
        Изображение в формате BGR размером (H, W, 3).
    target_dict : str, optional
        Имя целевого словаря ArUco для ускорения поиска.

    Возвращает:
    -----------
    Tuple[Optional[NDArray[np.float32]], Optional[int], Optional[str]]
        - corners : массив углов маркёра (4, 2) float32 или None.
        - marker_id : идентификатор обнаруженного маркёра.
        - dict_name : имя словаря, в котором маркёр был найден.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    dicts_to_try = ARUCO_DICTS
    if target_dict:
        dicts_to_try = [
            (n, d) for n, d in ARUCO_DICTS if target_dict.upper() in n
        ]

    for name, dict_id in dicts_to_try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners_list, ids, _ = detector.detectMarkers(gray)

        if ids is not None and len(ids) > 0:
            # Субпиксельное уточнение углов (точность ~0.1 пикселя)
            criteria = (cv2.TERM_CRITERIA_EPS +
                        cv2.TERM_CRITERIA_MAX_ITER, SUBPIXEL_CRITERIA_MAX_ITER, SUBPIXEL_CRITERIA_EPS)
            corners = cv2.cornerSubPix(
                gray,
                corners_list[0][0].astype(np.float32),
                winSize=SUBPIXEL_WIN_SIZE,
                zeroZone=SUBPIXEL_ZERO_ZONE,
                criteria=criteria
            )
            marker_id = int(ids[0][0])
            logger.info(f"ArUco найден: словарь={name}, ID={marker_id}")
            return corners, marker_id, name

    logger.warning("ArUco-маркёр не найден ни в одном словаре.")
    return None, None, None


def marker_side_px(corners: NDArray[np.float32]) -> float:
    """Вычисляет среднюю длину стороны маркёра в пикселях."""
    sides = [
        np.linalg.norm(corners[i] - corners[(i + 1) % 4])
        for i in range(4)
    ]
    return float(np.mean(sides))


def marker_center(corners: NDArray[np.float32]) -> Tuple[float, float]:
    """Вычисляет координаты центра маркёра в пикселях."""
    return (
        float(np.mean(corners[:, 0])),
        float(np.mean(corners[:, 1]))
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Оценка масштаба и вычисление габаритов
# ─────────────────────────────────────────────────────────────────────────────

class ScaleEstimator:
    """
    Вычисляет коэффициент масштаба (пиксели на метр) на основе
    ArUco-маркёра известного физического размера.

    Архитектурное назначение:
    -------------------------
    Класс инкапсулирует логику перехода от пиксельных координат
    к метрическим размерам, учитывая возможную разность глубин
    между маркёром и объектом (параметр same_plane).
    """

    def __init__(
        self,
        corners: NDArray[np.float32],
        marker_size_m: float,
        depth_map: Optional[NDArray[np.float32]] = None,
        same_plane: bool = True,
    ):
        """
        Параметры:
        ----------
        corners : NDArray[np.float32]
            Углы маркёра (4, 2) float32.
        marker_size_m : float
            Физический размер стороны маркёра в метрах.
        depth_map : NDArray[np.float32], optional
            Карта глубины для коррекции масштаба по глубине.
        same_plane : bool, optional
            Флаг: объект и маркёр находятся в одной плоскости.
        """
        self._corners = corners
        self._marker_size_m = marker_size_m
        self._depth_map = depth_map
        self._same_plane = same_plane

        self._side_px = self._compute_marker_side_px(corners)
        self._center_x, self._center_y = self._compute_marker_center(corners)

        # Оценка глубины до маркёра (медиана по окну 11×11 пикселей)
        self._marker_depth_m: Optional[float] = None
        if depth_map is not None:
            self._marker_depth_m = self._estimate_marker_depth(depth_map)

        # Базовый коэффициент масштаба у маркёра
        self._px_per_m_at_marker = self._side_px / marker_size_m

        logger.info(
            "Масштаб: %.2f px / %.1f mm = %.1f px/m",
            self._side_px,
            marker_size_m * 1000,
            self._px_per_m_at_marker,
        )

    @staticmethod
    def _compute_marker_side_px(corners: NDArray[np.float32]) -> float:
        """Вычисляет среднюю длину стороны маркёра в пикселях."""
        sides = [
            np.linalg.norm(corners[i] - corners[(i + 1) % 4])
            for i in range(4)
        ]
        return float(np.mean(sides))

    @staticmethod
    def _compute_marker_center(corners: NDArray[np.float32]) -> Tuple[float, float]:
        """Вычисляет координаты центра маркёра в пикселях."""
        return (
            float(np.mean(corners[:, 0])),
            float(np.mean(corners[:, 1])),
        )

    def _estimate_marker_depth(self, depth_map: NDArray[np.float32]) -> float:
        """Оценивает глубину до маркёра через медиану по окну 11×11."""
        height, width = depth_map.shape
        center_x_int = int(np.clip(self._center_x, 0, width - 1))
        center_y_int = int(np.clip(self._center_y, 0, height - 1))
        patch = 11
        y0 = max(0, center_y_int - patch // 2)
        y1 = min(height, center_y_int + patch // 2 + 1)
        x0 = max(0, center_x_int - patch // 2)
        x1 = min(width, center_x_int + patch // 2 + 1)
        return float(np.median(depth_map[y0:y1, x0:x1]))

    def px_per_m_at_depth(self, depth_m: float) -> float:
        """
        Корректирует коэффициент масштаба для объекта на другой глубине.

        Параметры:
        ----------
        depth_m : float
            Глубина объекта в метрах.

        Возвращает:
        -----------
        float
            Скорректированный коэффициент (пиксели на метр).
        """
        if (
            self._same_plane
            or self._marker_depth_m is None
            or self._marker_depth_m < 0.01
        ):
            return self._px_per_m_at_marker

        # Безопасная коррекция: ограничение влияния шумной глубины ±10%
        ratio = self._marker_depth_m / depth_m
        ratio = np.clip(ratio, 1.0 - ALIGNMENT_CORRECTION_TOLERANCE,
                        1.0 + ALIGNMENT_CORRECTION_TOLERANCE)
        return self._px_per_m_at_marker * ratio

    def measure_bbox(
        self,
        x1: int, y1: int, x2: int, y2: int,
    ) -> Dict[str, float]:
        """
        Вычисляет габариты ограничивающего прямоугольника в метрах.

        Параметры:
        ----------
        x1, y1, x2, y2 : int
            Координаты bbox в пикселях.

        Возвращает:
        -----------
        Dict[str, float]
            Словарь с размерами в метрах и пикселях, коэффициентом масштаба.
        """
        width_px = abs(x2 - x1)
        height_px = abs(y2 - y1)

        obj_depth_m: Optional[float] = None
        ppm: float = self._px_per_m_at_marker

        if self._depth_map is not None:
            height, width = self._depth_map.shape
            rx0 = int(np.clip(x1, 0, width - 1))
            ry0 = int(np.clip(y1, 0, height - 1))
            rx1 = int(np.clip(x2, 0, width - 1))
            ry1 = int(np.clip(y2, 0, height - 1))
            roi = self._depth_map[ry0:ry1, rx0:rx1]
            # Устойчивая оценка глубины: 10-й перцентиль (защита от выбросов)
            obj_depth_m = float(np.percentile(
                roi, 10)) if roi.size > 0 else self._marker_depth_m
            ppm = self.px_per_m_at_depth(obj_depth_m)

        result: Dict[str, float] = {
            "width_m": width_px / ppm,
            "height_m": height_px / ppm,
            "width_px": float(width_px),
            "height_px": float(height_px),
            "ppm": ppm,
        }
        if obj_depth_m is not None:
            result["depth_m"] = obj_depth_m

        return result


def measure_bbox_rotated(
    image: NDArray[np.uint8],
    bbox: Tuple[int, int, int, int],
    scale: ScaleEstimator
) -> Dict[str, float]:
    """
    Вычисляет габариты объекта с учётом поворота через minAreaRect.

    Архитектурное назначение:
    -------------------------
    Функция обеспечивает корректное определение ширины (ось X изображения)
    и высоты (ось Y изображения) для повёрнутых объектов, что необходимо
    для согласованности с системой координат контейнера в задаче упаковки.

    Параметры:
    ----------
    image : NDArray[np.uint8]
        Изображение BGR для извлечения контура.
    bbox : Tuple[int, int, int, int]
        Ограничивающий прямоугольник (x1, y1, x2, y2).
    scale : ScaleEstimator
        Экземпляр оценщика масштаба.

    Возвращает:
    -----------
    Dict[str, float]
        Габариты в метрах, пикселях, угол поворота, флаг rotated=True.
    """
    x1, y1, x2, y2 = bbox
    roi = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        # Фоллбэк на метод без учёта поворота
        return scale.measure_bbox(x1, y1, x2, y2)

    # Наибольший контур в ROI
    c = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)
    (center), (size_width, size_height), angle = rect

    # Явное определение ширины/высоты относительно осей изображения
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    min_x, max_x = np.min(box[:, 0]), np.max(box[:, 0])
    min_y, max_y = np.min(box[:, 1]), np.max(box[:, 1])

    w_px = max_x - min_x  # Размер по оси X
    h_px = max_y - min_y  # Размер по оси Y

    ppm = scale.px_per_m_at_marker
    width_m = w_px / ppm
    height_m = h_px / ppm

    # Глубина: медиана в исходном ROI (до поворота)
    depth_m: Optional[float] = None
    if scale._depth_map is not None:
        H, W = scale._depth_map.shape
        rx0 = int(np.clip(x1, 0, W - 1))
        ry0 = int(np.clip(y1, 0, H - 1))
        rx1 = int(np.clip(x2, 0, W - 1))
        ry1 = int(np.clip(y2, 0, H - 1))
        roi_depth = scale._depth_map[ry0:ry1, rx0:rx1]
        depth_m = (
            float(np.percentile(roi_depth, 10))
            if roi_depth.size > 0 else None
        )

    return {
        "width_m": width_m,
        "height_m": height_m,
        "width_px": float(w_px),
        "height_px": float(h_px),
        "depth_m": depth_m,
        "ppm": ppm,
        "rotated": True,
        "angle": float(angle)  # Для отладки и визуализации
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Автоматическая сегментация объекта по карте глубины
# ─────────────────────────────────────────────────────────────────────────────

def segment_object_from_depth(
    depth_map: NDArray[np.float32],
    image_bgr: NDArray[np.uint8],
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
    min_object_area_ratio: float = MIN_OBJECT_AREA_RATIO,
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    """
    Автоматически сегментирует объект из карты глубины методом Оцу.

    Параметры:
    ----------
    depth_map : NDArray[np.float32]
        Карта глубины (H, W) в метрах, float32.
    image_bgr : NDArray[np.uint8]
        Исходное изображение BGR для визуальной маскировки фона.
    marker_bbox : tuple, optional
        BBox маркёра для исключения из анализа.
    min_object_area_ratio : float, optional
        Минимальная доля площади объекта от кадра (по умолчанию 5%).

    Возвращает:
    -----------
    Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]
        (bbox, mask) или None при неудаче сегментации.
    """
    height, width = depth_map.shape

    # Исключаем область маркёра из анализа глубины
    depth_work = depth_map.copy()
    if marker_bbox is not None:
        x1, y1, x2, y2 = marker_bbox
        depth_work[y1:y2, x1:x2] = np.nan

    # Маска валидных пикселей глубины (0.1–10.0 м)
    valid_mask = (
        ~np.isnan(depth_work)
        & (depth_work > DEPTH_MIN_M)
        & (depth_work < DEPTH_MAX_M)
    )
    if valid_mask.sum() < MIN_VALID_PIXELS:
        logger.warning("Слишком мало валидных пикселей глубины: %d < %d",
                       valid_mask.sum(), MIN_VALID_PIXELS)
        return None

    # Нормализация глубины для бинаризации
    depth_valid = depth_work[valid_mask]
    depth_norm = np.zeros_like(depth_work)
    depth_range = depth_valid.max() - depth_valid.min() + 1e-5
    depth_norm[valid_mask] = (depth_valid - depth_valid.min()) / depth_range

    # Бинаризация методом Оцу (с фоллбэком)
    binary = _binarize_depth_map(depth_norm, valid_mask)

    # Морфологическая фильтрация шума
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, MORPH_KERNEL_SIZE)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN,
                              kernel, iterations=MORPH_OPEN_ITERATIONS)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE,
                              kernel, iterations=MORPH_CLOSE_ITERATIONS)

    # Поиск контуров
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        logger.warning("Контуры не найдены после морфологической обработки")
        return None

    # Выбор наибольшего контура
    min_area = height * width * min_object_area_ratio
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]

    if not valid_contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < min_area * 0.5:
            logger.warning(
                "Нет контуров > %.0f px, наибольший=%.0f px",
                min_area,
                cv2.contourArea(largest_contour),
            )
            return None
    else:
        largest_contour = max(valid_contours, key=cv2.contourArea)

    # Формирование bbox и маски
    x, y, w, h = cv2.boundingRect(largest_contour)
    bbox = (x, y, x + w, y + h)

    mask = np.zeros_like(binary, dtype=np.uint8)
    cv2.drawContours(mask, [largest_contour], -1, 255, thickness=cv2.FILLED)

    logger.info(
        "Объект сегментирован: bbox=%s, площадь=%.0f px",
        bbox,
        cv2.contourArea(largest_contour),
    )
    return bbox, mask.astype(bool)


def _binarize_depth_map(
    depth_norm: NDArray[np.float32],
    valid_mask: NDArray[np.bool_],
) -> NDArray[np.uint8]:
    """
    Выполняет бинаризацию нормализованной карты глубины методом Оцу.

    Параметры:
    ----------
    depth_norm : NDArray[np.float32]
        Нормализованная карта глубины [0, 1].
    valid_mask : NDArray[np.bool_]
        Маска валидных пикселей.

    Возвращает:
    -----------
    NDArray[np.uint8]
        Бинарное изображение (0/255).
    """
    try:
        from skimage.filters import threshold_otsu
        thresh_val = threshold_otsu(depth_norm[valid_mask])
        _, binary = cv2.threshold(
            (depth_norm * 255).astype(np.uint8),
            int(thresh_val * 255),
            255,
            cv2.THRESH_BINARY_INV,
        )
    except ImportError:
        logger.warning(
            "skimage не установлен, используется fallback-порог 127")
        _, binary = cv2.threshold(
            (depth_norm * 255).astype(np.uint8),
            127,
            255,
            cv2.THRESH_BINARY_INV,
        )
    return binary


# ─────────────────────────────────────────────────────────────────────────────
# 5. Визуализация результатов
# ─────────────────────────────────────────────────────────────────────────────

def enhance_depth_visualization(
    depth_map: NDArray[np.float32],
    bbox: Optional[Tuple[int, int, int, int]] = None,
    gamma: float = DEPTH_VIS_GAMMA,
    colormap: int = DEPTH_VIS_COLORMAP
) -> NDArray[np.uint8]:
    """
    Улучшает визуализацию карты глубины для отчётных материалов.

    Параметры:
    ----------
    depth_map : NDArray[np.float32]
        Карта глубины в метрах.
    bbox : tuple, optional
        BBox объекта для локальной нормализации.
    gamma : float, optional
        Коэффициент гамма-коррекции (по умолчанию 0.75).
    colormap : int, optional
        Colormap OpenCV (по умолчанию VIRIDIS).

    Возвращает:
    -----------
    NDArray[np.uint8]
        Визуализированная карта глубины BGR (H, W, 3), uint8.
    """
    # Локальная нормализация по области объекта
    if bbox:
        x1, y1, x2, y2 = bbox
        H, W = depth_map.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        if x2 > x1 and y2 > y1:
            roi_depth = depth_map[y1:y2, x1:x2]
            p_min, p_max = np.percentile(
                roi_depth, (DEPTH_VIS_PERCENTILE_LOW, DEPTH_VIS_PERCENTILE_HIGH))
        else:
            p_min, p_max = np.percentile(
                depth_map, (DEPTH_VIS_PERCENTILE_LOW, DEPTH_VIS_PERCENTILE_HIGH))
    else:
        p_min, p_max = np.percentile(
            depth_map, (DEPTH_VIS_PERCENTILE_LOW, DEPTH_VIS_PERCENTILE_HIGH))

    depth_range = p_max - p_min
    if depth_range < 1e-5:
        depth_norm = np.zeros_like(depth_map)
    else:
        depth_norm = np.clip(
            (depth_map - p_min) / (depth_range + 1e-5), 0.0, 1.0
        )

    # Гамма-коррекция для усиления контраста
    depth_norm = np.power(depth_norm, 1.0 / gamma)

    # Применение колормэпа
    depth_u8 = (depth_norm * 255).astype(np.uint8)
    depth_vis = cv2.applyColorMap(depth_u8, colormap)

    # Подсветка границ объекта
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(depth_vis, (x1, y1), (x2, y2),
                      (255, 255, 255), thickness=2)

    return depth_vis


def draw_marker(
    image: NDArray[np.uint8],
    corners: NDArray[np.float32],
    marker_id: int,
    marker_size_m: float
) -> None:
    """Отрисовывает маркёр и его физические размеры на изображении."""
    pts = corners.astype(int)
    cv2.polylines(image, [pts], isClosed=True, color=COLOR_MARKER, thickness=2)
    for pt in pts:
        cv2.circle(image, tuple(pt), radius=5,
                   color=COLOR_MARKER, thickness=-1)

    cx, cy = marker_center(corners)
    label = f"ArUco ID={marker_id} [{marker_size_m*1000:.1f}mm]"
    _put_label(image, label, int(cx), int(
        np.min(corners[:, 1])) - 12, COLOR_MARKER)


def draw_measurement(
    image: NDArray[np.uint8],
    x1: int, y1: int, x2: int, y2: int,
    measurements: Dict[str, float],
    label: str = "Объект",
) -> None:
    """Отрисовывает bbox объекта и аннотации с реальными размерами."""
    cv2.rectangle(image, (x1, y1), (x2, y2), COLOR_OBJECT, thickness=2)

    lines = [
        f"{label}",
        f"W: {measurements['width_m']*100:.1f} cm",
        f"H: {measurements['height_m']*100:.1f} cm",
    ]
    if "depth_m" in measurements and measurements["depth_m"] is not None:
        lines.append(f"Z: {measurements['depth_m']:.2f} m")

    tx, ty = x1, y1 - 10 - (len(lines) - 1) * 22
    for line in lines:
        _put_label(image, line, tx, ty, COLOR_OBJECT)
        ty += 22

    _draw_dimension_arrow(
        image, x1, y2 + 15, x2, y2 + 15,
        f"{measurements['width_m']*100:.1f} cm", COLOR_OBJECT
    )
    _draw_dimension_arrow(
        image, x2 + 15, y1, x2 + 15, y2,
        f"{measurements['height_m']*100:.1f} cm", COLOR_OBJECT, vertical=True
    )


def _put_label(
    image: NDArray[np.uint8],
    text: str,
    x: int, y: int,
    color: Tuple[int, int, int]
) -> None:
    """Вспомогательная функция: отрисовка текста на полупрозрачном фоне."""
    (text_width, text_height), _ = cv2.getTextSize(
        text, FONT, FONT_SCALE, FONT_THICKNESS
    )
    cv2.rectangle(
        image,
        (x - 2, y - text_height - 4),
        (x + text_width + 2, y + 4),
        COLOR_BACKGROUND,
        thickness=-1,
    )
    cv2.putText(
        image,
        text,
        (x, y),
        FONT,
        FONT_SCALE,
        color,
        thickness=FONT_THICKNESS,
        lineType=LINE_TYPE,
    )


def _draw_dimension_arrow(
    image: NDArray[np.uint8],
    x1: int, y1: int, x2: int, y2: int,
    label: str,
    color: Tuple[int, int, int],
    vertical: bool = False
) -> None:
    """Вспомогательная функция: отрисовка размерной стрелки с подписью."""
    cv2.arrowedLine(image, (x1, y1), (x2, y2), color,
                    thickness=1, tipLength=0.05)
    cv2.arrowedLine(image, (x2, y2), (x1, y1), color,
                    thickness=1, tipLength=0.05)
    mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
    _put_label(image, label, mid_x, mid_y, color)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Публичный API: автоматический конвейер измерения
# ─────────────────────────────────────────────────────────────────────────────

def measure_object_auto(
    image_bgr: NDArray[np.uint8],
    marker_size_m: float,
    depth_map: NDArray[np.float32],
    aruco_dict: Optional[str] = None,
    object_label: str = "Объект",
    same_plane: bool = True,
    enable_alignment: bool = True,
    reference_angle_deg: float = 0.0,
) -> Tuple[Optional[Dict[str, float]], NDArray[np.uint8], Optional[NDArray[np.bool_]]]:
    """
    Полностью автоматический конвейер измерения габаритов.

    Последовательность операций:
    ---------------------------
    1. Детекция ArUco-маркёра с субпиксельным уточнением.
    2. Вычисление масштаба (пиксели на метр) по известному размеру маркёра.
    3. Автоматическая сегментация объекта по карте глубины.
    4. [Опционально] Выравнивание объекта относительно сетки площадки.
    5. Вычисление габаритов через axis-aligned bounding box.
    6. Визуализация результатов с аннотациями.

    Параметры:
    ----------
    image_bgr : NDArray[np.uint8]
        Исходное изображение BGR.
    marker_size_m : float
        Физический размер стороны маркёра в метрах.
    depth_map : NDArray[np.float32]
        Карта глубины в метрах (H, W), float32.
    aruco_dict : str, optional
        Имя целевого словаря ArUco для ускорения детекции.
    object_label : str, optional
        Подпись объекта для визуализации.
    same_plane : bool, optional
        Флаг: объект и маркёр в одной плоскости (по умолчанию True).
    enable_alignment : bool, optional
        Включить выравнивание объекта (по умолчанию True, из config).
    reference_angle_deg : float, optional
        Угол эталонной оси сетки (по умолчанию 0.0 = горизонталь).

    Возвращает:
    -----------
    Tuple[Optional[Dict[str, float]], NDArray[np.uint8], Optional[NDArray[np.bool_]]]
        - measurements : словарь с габаритами в метрах или None при ошибке.
        - annotated_image : изображение с отрисованными результатами.
        - object_mask : бинарная маска объекта или None.
    """
    result_img = image_bgr.copy()

    # 1. Детекция маркёра
    corners, marker_id, dict_name = detect_aruco(image_bgr, aruco_dict)
    if corners is None:
        logger.error("Маркёр не найден")
        return None, result_img, None

    marker_bbox_cv = cv2.boundingRect(corners.astype(np.float32))
    marker_bbox = tuple(marker_bbox_cv)
    draw_marker(result_img, corners, marker_id, marker_size_m)

    # 2. Оценка масштаба
    scale = ScaleEstimator(corners, marker_size_m,
                           depth_map, same_plane=same_plane)

    # 3. Сегментация объекта
    seg_result = segment_object_from_depth(
        depth_map, image_bgr, marker_bbox=marker_bbox
    )
    if seg_result is None:
        logger.error("Не удалось сегментировать объект автоматически")
        return None, result_img, None

    bbox, object_mask = seg_result

    # 4. [Опционально] Выравнивание объекта относительно сетки
    if enable_alignment and getattr(settings, 'cv_enable_alignment', True):
        logger.info("Применение выравнивания объекта...")
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        aligned_img, aligned_depth, aligned_mask, detected_angle = align_object_to_grid(
            image_rgb=image_rgb,
            depth_map=depth_map,
            object_mask=object_mask,
            reference_angle_deg=reference_angle_deg,
        )
        # Возврат к BGR для совместимости с остальным конвейером
        image_bgr = cv2.cvtColor(aligned_img, cv2.COLOR_RGB2BGR)
        depth_map = aligned_depth
        object_mask = aligned_mask
        # Пересчёт bbox на выровненном изображении
        contours, _ = cv2.findContours(
            object_mask.astype(
                np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if contours:
            cnt = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(cnt)
            bbox = (x, y, x + w, y + h)

    # 5. Вычисление габаритов (на выровненном изображении — axis-aligned)
    measurements = measure_bbox_rotated(image_bgr, bbox, scale)

    # 6. Визуализация
    draw_measurement(
        result_img, bbox[0], bbox[1], bbox[2], bbox[3],
        measurements, object_label
    )
    # Полупрозрачная маска для наглядности
    mask_overlay = result_img.copy()
    mask_overlay[object_mask] = (
        mask_overlay[object_mask] * 0.7 + np.array([0, 255, 0]) * 0.3
    ).astype(np.uint8)
    cv2.addWeighted(mask_overlay, 0.5, result_img, 0.5, 0, result_img)

    logger.info(
        "Результат [%s]: W=%.1f cm, H=%.1f cm",
        object_label,
        measurements['width_m']*100,
        measurements['height_m']*100
    )
    return measurements, result_img, object_mask


def measure_from_wrapper(
    image_bgr: NDArray[np.uint8],
    wrapper,  # DepthAnythingV2OpenVINO instance
    marker_size_m: float,
    multi_scale: bool = False,
    object_label: str = "Объект",
    same_plane: bool = True,
    enhance_visualization: bool = True,
    gamma: float = DEPTH_VIS_GAMMA,
) -> Tuple[Optional[Dict[str, float]], NDArray[np.uint8], NDArray[np.uint8]]:
    """
    Конвейер измерения с использованием обёртки глубинной модели.

    Параметры:
    ----------
    wrapper : DepthAnythingV2OpenVINO
        Экземпляр модели оценки глубины.
    ... (остальные параметры как в measure_object_auto)

    Возвращает:
    -----------
    Tuple[measurements, annotated_image, depth_visualization]
    """
    logger.info("Запуск Depth Anything V2 (metric depth)...")
    depth_map = wrapper.estimate_multi_scale(
        image_bgr, multi_scale=multi_scale)

    # Визуализация глубины
    if enhance_visualization:
        logger.info("Применение улучшенной визуализации (VIRIDIS)...")
        depth_vis = enhance_depth_visualization(
            depth_map, bbox=None, gamma=gamma, colormap=DEPTH_VIS_COLORMAP
        )
    else:
        depth_vis = wrapper.estimate_visual(
            image_bgr, normalize="metric_range", multi_scale=multi_scale
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
# 7. CLI-интерфейс для автономного тестирования
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    """Парсер аргументов командной строки для тестового запуска."""
    parser = argparse.ArgumentParser(
        description="ArUco object measurement (Auto Mode)"
    )
    parser.add_argument(
        "--image", required=True, help="Путь к входному изображению"
    )
    parser.add_argument(
        "--marker-size", type=float, default=0.055,
        help="Размер маркёра в метрах (default: 0.055)"
    )
    parser.add_argument(
        "--output", default="measurement_result.jpg",
        help="Путь к выходному файлу"
    )
    parser.add_argument(
        "--label", default="Object", help="Подпись объекта"
    )
    parser.add_argument(
        "--gamma", type=float, default=DEPTH_VIS_GAMMA,
        help="Гамма-коррекция для визуализации глубины"
    )
    parser.add_argument(
        "--no-align", action="store_true",
        help="Отключить выравнивание объекта"
    )
    return parser.parse_args()
