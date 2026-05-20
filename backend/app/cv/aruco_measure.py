"""
aruco_measure.py
Модуль измерения габаритов объектов по 2D-изображениям с использованием ArUco-маркера
и монокулярной оценки глубины.
Включает поддержку ручной области интереса (ROI) и коррекцию перспективы.
"""
import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List
import cv2
import numpy as np
from numpy.typing import NDArray
from app.core.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Константы модуля
# ─────────────────────────────────────────────────────────────────────────────
ARUCO_DICTS: List[Tuple[str, int]] = [
    ("4X4_50", cv2.aruco.DICT_4X4_50),
    ("4X4_100", cv2.aruco.DICT_4X4_100),
    ("4X4_250", cv2.aruco.DICT_4X4_250),
    ("5X5_50", cv2.aruco.DICT_5X5_50),
    ("5X5_100", cv2.aruco.DICT_5X5_100),
    ("6X6_50", cv2.aruco.DICT_6X6_50),
    ("6X6_100", cv2.aruco.DICT_6X6_100),
    ("ORIGINAL", cv2.aruco.DICT_ARUCO_ORIGINAL),
]

FONT: int = cv2.FONT_HERSHEY_SIMPLEX
COLOR_MARKER: Tuple[int, int, int] = (0, 255, 0)
COLOR_OBJECT: Tuple[int, int, int] = (255, 100, 0)
COLOR_TEXT: Tuple[int, int, int] = (255, 255, 255)
COLOR_BACKGROUND: Tuple[int, int, int] = (30, 30, 30)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Детекция ArUco-маркёра
# ─────────────────────────────────────────────────────────────────────────────
def detect_aruco(
    image_bgr: NDArray[np.uint8],
    target_dict: Optional[str] = None,
    expected_marker_id: Optional[int] = None,
) -> Tuple[Optional[NDArray[np.float32]], Optional[int], Optional[str]]:
    """
    Ищет ArUco-маркёр в изображении с субпиксельным уточнением углов.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    dicts_to_try = ARUCO_DICTS
    if target_dict:
        dicts_to_try = [(n, d) for n, d in ARUCO_DICTS if target_dict.upper() in n]

    for name, dict_id in dicts_to_try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners_list, ids, _ = detector.detectMarkers(gray)
        
        if ids is not None and len(ids) > 0:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(
                gray,
                corners_list[0][0].astype(np.float32),
                winSize=(11, 11),
                zeroZone=(-1, -1),
                criteria=criteria
            )
            marker_id = int(ids[0][0])
            if expected_marker_id is not None and marker_id != expected_marker_id:
                continue
            
            logger.info(f"ArUco найден: словарь={name}, ID={marker_id}")
            return corners, marker_id, name

    logger.warning("ArUco-маркёр не найден ни в одном словаре.")
    return None, None, None

def marker_side_px(corners: NDArray[np.float32]) -> float:
    """Вычисляет среднюю длину стороны маркёра в пикселях."""
    sides = [np.linalg.norm(corners[i] - corners[(i + 1) % 4]) for i in range(4)]
    return float(np.mean(sides))

def marker_center(corners: NDArray[np.float32]) -> Tuple[float, float]:
    """Вычисляет координаты центра маркёра в пикселях."""
    return float(np.mean(corners[:, 0])), float(np.mean(corners[:, 1]))

# ─────────────────────────────────────────────────────────────────────────────
# 2. Оценка масштаба (Scale Estimator)
# ─────────────────────────────────────────────────────────────────────────────
class ScaleEstimator:
    """
    Вычисляет коэффициент масштаба (пиксели на метр) на основе
    ArUco-маркёра известного физического размера.
    """
    def __init__(self, corners, marker_size_m, depth_map=None, same_plane=True):
        self.corners = corners
        self.marker_size_m = marker_size_m
        self.depth_map = depth_map
        self.same_plane = same_plane
        
        self._side_px = marker_side_px(corners)
        self._cx, self._cy = marker_center(corners)

        if depth_map is not None:
            h, w = depth_map.shape
            cx_i, cy_i = int(np.clip(self._cx, 0, w - 1)), int(np.clip(self._cy, 0, h - 1))
            patch = 11
            y0 = max(0, cy_i - patch // 2); y1 = min(h, cy_i + patch // 2 + 1)
            x0 = max(0, cx_i - patch // 2); x1 = min(w, cx_i + patch // 2 + 1)
            self.marker_depth_m = float(np.median(depth_map[y0:y1, x0:x1]))
        else:
            self.marker_depth_m = None

        # Этот атрибут создавался, но не работал из-за ошибки в названии метода
        self.px_per_m_at_marker = self._side_px / marker_size_m
        # Внутренний атрибут для методов, которые используют его как защищённый
        self._px_per_m_at_marker = self.px_per_m_at_marker
        
        logger.info(
            f"Масштаб: {self._side_px:.2f} px / {marker_size_m*1000:.1f} mm "
            f"= {self.px_per_m_at_marker:.1f} px/m"
        )

    def _estimate_marker_depth(self, depth_map: NDArray[np.float32]) -> float:
        """Оценивает глубину до маркёра через медиану по окну 11x11."""
        height, width = depth_map.shape
        cx = int(np.clip(self._center_x, 0, width - 1))
        cy = int(np.clip(self._center_y, 0, height - 1))
        patch = 11
        y0, y1 = max(0, cy - 5), min(height, cy + 6)
        x0, x1 = max(0, cx - 5), min(width, cx + 6)
        return float(np.median(depth_map[y0:y1, x0:x1]))

    def px_per_m_at_depth(self, depth_m: float) -> float:
        """Корректирует коэффициент масштаба для объекта на другой глубине."""
        if self._same_plane or self._marker_depth_m is None or self._marker_depth_m < 0.01:
            return self.px_per_m_at_marker   
        ratio = self._marker_depth_m / depth_m
        ratio = np.clip(ratio, 0.90, 1.10)
        return self._px_per_m_at_marker * ratio

    def measure_bbox(self, x1: int, y1: int, x2: int, y2: int) -> Dict[str, float]:
        """Вычисляет габариты ограничивающего прямоугольника в метрах."""
        width_px = abs(x2 - x1)
        height_px = abs(y2 - y1)
        obj_depth_m: Optional[float] = None
        ppm: float = self.px_per_m_at_marker
        
        if self.depth_map is not None:
            height, width = self.depth_map.shape
            rx0 = int(np.clip(x1, 0, width - 1))
            ry0 = int(np.clip(y1, 0, height - 1))
            rx1 = int(np.clip(x2, 0, width - 1))
            ry1 = int(np.clip(y2, 0, height - 1))
            roi = self.depth_map[ry0:ry1, rx0:rx1]
            obj_depth_m = float(np.percentile(roi, 10)) if roi.size > 0 else self._marker_depth_m
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

# ─────────────────────────────────────────────────────────────────────────────
# 3. Статистическая коррекция перспективы
# ─────────────────────────────────────────────────────────────────────────────
def apply_perspective_correction_statistical(
    measurements: Dict[str, float],
    depth_map: NDArray[np.float32],
    bbox: Tuple[int, int, int, int]
) -> Dict[str, float]:
    """
    Статистическая коррекция перспективы на основе карты глубины.
    Анализирует градиенты глубины для определения наклона объекта.
    """
    x1, y1, x2, y2 = bbox
    # Обрезаем глубину по bbox
    roi_depth = depth_map[y1:y2, x1:x2]
    valid_depth = roi_depth[~np.isnan(roi_depth)]

    if len(valid_depth) < 100:
        return measurements

    # Статистики
    depth_mean = np.median(valid_depth)
    depth_std = np.std(valid_depth)
    cv = depth_std / depth_mean if depth_mean > 0 else 0

    # Если объект "плоский" относительно камеры, коррекция не нужна
    if cv < 0.05: 
        measurements['perspective_method'] = 'none'
        return measurements

    # Градиенты для определения направления наклона
    grad_x = np.gradient(roi_depth, axis=1)
    grad_y = np.gradient(roi_depth, axis=0)
    valid_grad = ~np.isnan(roi_depth)
    
    slope_x = np.median(np.abs(grad_x[valid_grad])) if np.any(valid_grad) else 0
    slope_y = np.median(np.abs(grad_y[valid_grad])) if np.any(valid_grad) else 0

    # Эвристические коэффициенты (настроены под Depth Anything V2)
    k = 2.5
    m = 0.35
    base_factor = 1.0 + np.tanh(cv * k) * m

    # Асимметричная коррекция на основе градиентов
    correction_x = base_factor * (1.0 + slope_x * 0.5)
    correction_y = base_factor * (1.0 + slope_y * 0.5)

    # Учёт соотношения сторон для уточнения
    w_px = x2 - x1
    h_px = y2 - y1
    aspect = min(w_px, h_px) / max(w_px, h_px) if max(w_px, h_px) > 0 else 1.0

    if aspect < 0.7:
        if w_px > h_px: correction_x *= 1.1
        else: correction_y *= 1.1

    # Применяем коррекцию
    corrected = measurements.copy()
    corrected['width_m'] *= correction_x
    corrected['height_m'] *= correction_y
    corrected['perspective_method'] = 'statistical'
    corrected['correction_factor'] = (float(correction_x), float(correction_y))
    
    logger.info(f"Применена стат. коррекция перспективы: CV={cv:.2f}, Factors=({correction_x:.2f}, {correction_y:.2f})")
    return corrected

# ─────────────────────────────────────────────────────────────────────────────
# 4. Измерение (bbox rotated)
# ─────────────────────────────────────────────────────────────────────────────
def measure_bbox_rotated(
    image: NDArray[np.uint8],
    bbox: Tuple[int, int, int, int],
    scale: ScaleEstimator,
    padding_px: float = 10.0
) -> Dict[str, float]:
    """
    Вычисляет габариты объекта с учётом поворота через minAreaRect.
    ВАЖНО: Все координаты возвращаются в системе координат исходного изображения.
    """
    x1, y1, x2, y2 = bbox
    
    # Локальный ROI для извлечения контура (не изменяет систему координат!)
    roi = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return scale.measure_bbox(x1, y1, x2, y2)

    c = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)
    box = cv2.boxPoints(rect)  # Координаты ОТНОСИТЕЛЬНО (0,0) ROI
    box = np.int0(box)

    # 🔥 КОНВЕРТАЦИЯ: локальные → глобальные координаты
    min_x = x1 + np.min(box[:, 0])  # Глобальная координата в исходном изображении
    max_x = x1 + np.max(box[:, 0])
    min_y = y1 + np.min(box[:, 1])
    max_y = y1 + np.max(box[:, 1])

    # Размеры в пикселях (глобальные)
    w_px = max_x - min_x
    h_px = max_y - min_y
    
    ppm = scale.px_per_m_at_marker
    width_m = w_px / ppm
    height_m = h_px / ppm

    # Глубина: используем глобальные координаты для выборки из depth_map
    depth_m: Optional[float] = None
    if scale._depth_map is not None:
        H, W = scale._depth_map.shape
        rx0 = int(np.clip(min_x, 0, W - 1))
        ry0 = int(np.clip(min_y, 0, H - 1))
        rx1 = int(np.clip(max_x, 0, W - 1))
        ry1 = int(np.clip(max_y, 0, H - 1))
        roi_depth = scale._depth_map[ry0:ry1, rx0:rx1]
        depth_m = float(np.percentile(roi_depth, 10)) if roi_depth.size > 0 else None

    # Padding применяем к глобальным координатам
    h_img, w_img = image.shape[:2]
    min_x = max(0, min_x - padding_px)
    max_x = min(w_img, max_x + padding_px)
    min_y = max(0, min_y - padding_px)
    max_y = min(h_img, max_y + padding_px)

    return {
        "width_m": width_m,
        "height_m": height_m,
        "width_px": float(max_x - min_x),
        "height_px": float(max_y - min_y),
        "depth_m": depth_m,
        "ppm": ppm,
        "rotated": True,
    }

# ─────────────────────────────────────────────────────────────────────────────
# 5. Автоматическая сегментация с поддержкой Manual ROI
# ─────────────────────────────────────────────────────────────────────────────
def segment_object_from_depth(
    depth_map: NDArray[np.float32],
    image_bgr: NDArray[np.uint8],
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
    min_object_area_ratio: float = 0.02,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    """
    Автоматически сегментирует объект из карты глубины методом Оцу.
    Поддерживает ручное указание ROI для улучшения сегментации.
    """
    height, width = depth_map.shape
    
    # Исключаем область маркёра
    depth_work = depth_map.copy()
    if marker_bbox is not None:
        x1, y1, x2, y2 = marker_bbox
        depth_work[y1:y2, x1:x2] = np.nan

    # Маска валидных пикселей
    valid_mask = (~np.isnan(depth_work) & (depth_work > 0.1) & (depth_work < 10.0))
    if valid_mask.sum() < 100:
        return None

    # Нормализация
    depth_valid = depth_work[valid_mask]
    depth_norm = np.zeros_like(depth_work)
    depth_range = depth_valid.max() - depth_valid.min() + 1e-5
    depth_norm[valid_mask] = (depth_valid - depth_valid.min()) / depth_range

    # Бинаризация
    try:
        from skimage.filters import threshold_otsu
        thresh_val = threshold_otsu(depth_norm[valid_mask])
        _, binary = cv2.threshold(
            (depth_norm * 255).astype(np.uint8),
            int(thresh_val * 255), 255, cv2.THRESH_BINARY_INV
        )
    except ImportError:
        _, binary = cv2.threshold(
            (depth_norm * 255).astype(np.uint8),
            127, 255, cv2.THRESH_BINARY_INV
        )

    # 🔥 Применение Manual ROI (если задан)
    if manual_roi is not None:
        rx1, ry1, rx2, ry2 = manual_roi
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(width, rx2), min(height, ry2)
        if rx2 > rx1 and ry2 > ry1:
            roi_mask = np.zeros_like(binary)
            roi_mask[ry1:ry2, rx1:rx2] = 255
            binary = cv2.bitwise_and(binary, roi_mask)
            logger.info(f"Применен Manual ROI: {manual_roi}")

    # Морфология
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # Контур
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    min_area = height * width * min_object_area_ratio
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    
    if not valid_contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < min_area * 0.5:
            return None
    else:
        largest_contour = max(valid_contours, key=cv2.contourArea)

    x, y, w, h = cv2.boundingRect(largest_contour)
    bbox = (x, y, x + w, y + h)
    mask = np.zeros_like(binary, dtype=np.uint8)
    cv2.drawContours(mask, [largest_contour], -1, 255, thickness=cv2.FILLED)
    

    return bbox, mask.astype(bool)

# ─────────────────────────────────────────────────────────────────────────────
# 6. Визуализация и API
# ─────────────────────────────────────────────────────────────────────────────
def draw_marker(image, corners, marker_id, marker_size_m):
    pts = corners.astype(int)
    cv2.polylines(image, [pts], isClosed=True, color=COLOR_MARKER, thickness=2)
    cx, cy = marker_center(corners)
    label = f"ArUco ID={marker_id} [{marker_size_m*1000:.1f}mm]"
    cv2.putText(image, label, (int(cx)-50, int(cy)-50), FONT, 0.6, COLOR_MARKER, 2)

def draw_measurement(image, x1, y1, x2, y2, measurements, label="Объект"):
    cv2.rectangle(image, (x1, y1), (x2, y2), COLOR_OBJECT, 2)
    lines = [
        label,
        f"W: {measurements['width_m']*100:.1f} cm",
        f"H: {measurements['height_m']*100:.1f} cm"
    ]
    ty = y1 - 10
    for line in lines:
        cv2.putText(image, line, (x1, ty), FONT, 0.6, COLOR_TEXT, 2)
        ty -= 22

def measure_object_auto(
    image_bgr: NDArray[np.uint8],
    marker_size_m: float,
    depth_map: NDArray[np.float32],
    aruco_dict: Optional[str] = None,
    object_label: str = "Объект",
    same_plane: bool = True,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    expected_marker_id: Optional[int] = None,
) -> Tuple[Optional[Dict[str, float]], NDArray[np.uint8], Optional[NDArray[np.bool_]]]:
    """Полностью автоматический конвейер измерения габаритов."""
    result_img = image_bgr.copy()
    
    # 1. Маркёр
    corners, marker_id, _ = detect_aruco(image_bgr, aruco_dict, expected_marker_id)
    if corners is None:
        return None, result_img, None
    
    marker_bbox_cv = cv2.boundingRect(corners.astype(np.float32))
    marker_bbox = tuple(marker_bbox_cv)
    draw_marker(result_img, corners, marker_id, marker_size_m)

    # 2. Масштаб
    scale = ScaleEstimator(corners, marker_size_m, depth_map, same_plane=same_plane)

    # 3. Сегментация (с поддержкой Manual ROI)
    seg_result = segment_object_from_depth(
        depth_map, image_bgr, marker_bbox=marker_bbox, manual_roi=manual_roi
    )
    if seg_result is None:
        return None, result_img, None

    bbox, object_mask = seg_result
    
    # 4. Измерение (включает внутреннюю коррекцию перспективы)
    measurements = measure_bbox_rotated(result_img, bbox, scale)
    draw_measurement(result_img, bbox[0], bbox[1], bbox[2], bbox[3], measurements, object_label)

    return measurements, result_img, object_mask

def measure_from_wrapper(
    image_bgr: NDArray[np.uint8],
    wrapper,
    marker_size_m: float,
    multi_scale: bool = False,
    object_label: str = "Объект",
    same_plane: bool = True,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    expected_marker_id: Optional[int] = None,
) -> Tuple[Optional[Dict[str, float]], NDArray[np.uint8], NDArray[np.uint8]]:
    """Конвейер измерения с использованием обёртки глубинной модели."""
    logger.info("Запуск Depth Anything V2 (metric depth)...")
    depth_map = wrapper.estimate(image_bgr, multi_scale=multi_scale)
    
    # Визуализация глубины
    depth_vis = wrapper.estimate_visual(image_bgr, normalize="metric_range", multi_scale=multi_scale)

    # Автоматическое измерение
    measurements, annotated, object_mask = measure_object_auto(
        image_bgr,
        marker_size_m=marker_size_m,
        depth_map=depth_map,
        object_label=object_label,
        same_plane=same_plane,
        manual_roi=manual_roi,
        expected_marker_id=expected_marker_id,
    )
    return measurements, annotated, depth_vis