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
    v2: Улучшенная бинаризация для сетчатых ковриков + исправление бага поиска ID.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # 🔥 УЛУЧШЕНИЕ 1: Выравнивание контраста (CLAHE)
    # Помогает выделить маркёр, если освещение неравномерное или сетка коврика слишком яркая
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray_enhanced = clahe.apply(gray)

    dicts_to_try = ARUCO_DICTS
    if target_dict:
        dicts_to_try = [(n, d)
                        for n, d in ARUCO_DICTS if target_dict.upper() in n]

    for name, dict_id in dicts_to_try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        params = cv2.aruco.DetectorParameters()

        # 🔥 УЛУЧШЕНИЕ 2: Расширенный поиск порога бинаризации
        # По умолчанию max=23, но для ковриков с сеткой нужны большие окна, чтобы размыть сетку
        params.adaptiveThreshWinSizeMin = 3
        params.adaptiveThreshWinSizeMax = 40  # Увеличено!
        params.adaptiveThreshWinSizeStep = 5  # Шаг увеличен для скорости

        # Более мягкая фильтрация углов (для фото под углом)
        params.polygonalApproxAccuracyRate = 0.05  # Было 0.03 по умолчанию

        # Настройки субпиксельного уточнения
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.cornerRefinementMinAccuracy = 0.05

        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        corners_list, ids, _ = detector.detectMarkers(gray_enhanced)

        if ids is not None and len(ids) > 0:
            # 🔥 ИСПРАВЛЕНИЕ БАГА 3: Перебираем ВСЕ найденные маркёры!
            # Раньше код брал только ids[0], и если это был мусор с коврика,
            # он игнорировал настоящий маркёр.
            target_idx = 0
            if expected_marker_id is not None:
                found = False
                for i, mid in enumerate(ids):
                    if int(mid[0]) == expected_marker_id:
                        target_idx = i
                        found = True
                        break
                if not found:
                    # В этом словаре нет нужного ID, переходим к следующему
                    continue

            criteria = (cv2.TERM_CRITERIA_EPS +
                        cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            # Уточняем углы на усиленном изображении для большей точности
            corners = cv2.cornerSubPix(
                gray_enhanced,
                corners_list[target_idx][0].astype(np.float32),
                winSize=(11, 11),
                zeroZone=(-1, -1),
                criteria=criteria
            )
            marker_id = int(ids[target_idx][0])

            logger.info(f"ArUco найден: словарь={name}, ID={marker_id}")
            return corners, marker_id, name

    logger.warning("ArUco-маркёр не найден ни в одном словаре.")
    return None, None, None


def marker_side_px(corners: NDArray[np.float32]) -> float:
    """Вычисляет среднюю длину стороны маркёра в пикселях."""
    sides = [np.linalg.norm(corners[i] - corners[(i + 1) % 4])
             for i in range(4)]
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
        if self.same_plane or self.marker_depth_m is None or self.marker_depth_m < 0.01:
            return self.px_per_m_at_marker
        ratio = self.marker_depth_m / depth_m
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
            obj_depth_m = float(np.percentile(
                roi, 10)) if roi.size > 0 else self.marker_depth_m
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

    slope_x = np.median(np.abs(grad_x[valid_grad])) if np.any(
        valid_grad) else 0
    slope_y = np.median(np.abs(grad_y[valid_grad])) if np.any(
        valid_grad) else 0

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
        if w_px > h_px:
            correction_x *= 1.1
        else:
            correction_y *= 1.1

    # Применяем коррекцию
    corrected = measurements.copy()
    corrected['width_m'] *= correction_x
    corrected['height_m'] *= correction_y
    corrected['perspective_method'] = 'statistical'
    corrected['correction_factor'] = (float(correction_x), float(correction_y))

    logger.info(
        f"Применена стат. коррекция перспективы: CV={cv:.2f}, Factors=({correction_x:.2f}, {correction_y:.2f})")
    return corrected

# ─────────────────────────────────────────────────────────────────────────────
# 4. Измерение с учётом поворота (FIX v5 — возврат к v3 + улучшения)
# ─────────────────────────────────────────────────────────────────────────────


def measure_bbox_rotated(
    image: NDArray[np.uint8],
    bbox: Tuple[int, int, int, int],
    scale: ScaleEstimator,
    object_mask: Optional[NDArray[np.bool_]] = None,  # ДОБАВЛЕН ПАРАМЕТР
    padding_px: float = 10.0
) -> Dict[str, float]:
    """
    Вычисляет габариты объекта с учётом поворота через minAreaRect.
    v2: Использует точную маску (GrabCut), если она передана.
    """
    x1, y1, x2, y2 = bbox
    rect = None

    # Приоритет: используем точную маску, если она есть
    if object_mask is not None:
        roi_mask = (object_mask[y1:y2, x1:x2]).astype(np.uint8) * 255
        contours, _ = cv2.findContours(
            roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(c)

    # Fallback: старый метод через порог по RGB, если маски нет
    if rect is None:
        roi = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(c)

    if rect is None:
        return scale.measure_bbox(x1, y1, x2, y2)

    w_px_rot, h_px_rot = rect[1]
    w_px_rot = float(w_px_rot)
    h_px_rot = float(h_px_rot)

    if w_px_rot < h_px_rot:
        w_px_rot, h_px_rot = h_px_rot, w_px_rot

    cx_local, cy_local = rect[0]
    cx_global = x1 + cx_local
    cy_global = y1 + cy_local

    ppm = scale.px_per_m_at_marker

    depth_m: Optional[float] = None
    if scale.depth_map is not None:
        H, W = scale.depth_map.shape
        gx = int(np.clip(cx_global, 0, W - 1))
        gy = int(np.clip(cy_global, 0, H - 1))
        depth_m = float(scale.depth_map[gy, gx])
        ppm = scale.px_per_m_at_depth(depth_m)

    width_m = w_px_rot / ppm
    height_m = h_px_rot / ppm

    box = cv2.boxPoints(rect)
    box[:, 0] += x1
    box[:, 1] += y1
    min_x = float(np.min(box[:, 0]) - padding_px)
    max_x = float(np.max(box[:, 0]) + padding_px)
    min_y = float(np.min(box[:, 1]) - padding_px)
    max_y = float(np.max(box[:, 1]) + padding_px)

    h_img, w_img = image.shape[:2]
    min_x = max(0.0, min_x)
    max_x = min(float(w_img), max_x)
    min_y = max(0.0, min_y)
    max_y = min(float(h_img), max_y)

    return {
        "width_m": width_m,
        "height_m": height_m,
        "width_px": w_px_rot,
        "height_px": h_px_rot,
        "depth_m": depth_m,
        "ppm": ppm,
        "rotated": True,
        "angle_deg": float(rect[2]),
        "viz_bbox": (int(min_x), int(min_y), int(max_x), int(max_y)),
    }

# ─────────────────────────────────────────────────────────────────────────────
# 5. Сегментация объектов по разрывам глубины — FIX v5 (v3 + восстановление краёв)
# ─────────────────────────────────────────────────────────────────────────────


def _build_edges_from_depth(
    depth_work: NDArray[np.float32],
    valid_mask: NDArray[np.bool_],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    v10: 7x7 blur (как работало для коробки) + резервный канал.
    """
    median_depth = float(np.nanmedian(
        depth_work[valid_mask])) if np.any(valid_mask) else 1.0
    depth_filled = np.where(valid_mask, depth_work,
                            median_depth).astype(np.float32)
    depth_smooth = cv2.GaussianBlur(depth_filled, (7, 7), 0)

    sobel_x = cv2.Sobel(depth_smooth, cv2.CV_32F, 1, 0, ksize=5)
    sobel_y = cv2.Sobel(depth_smooth, cv2.CV_32F, 0, 1, ksize=5)
    magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
    magnitude[~valid_mask] = 0.0

    mag_norm = cv2.normalize(magnitude, None, 0, 255,
                             cv2.NORM_MINMAX).astype(np.uint8)
    if mag_norm.max() == 0:
        return np.zeros_like(mag_norm), depth_smooth

    _, edges = cv2.threshold(
        mag_norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Резервный канал для плоских сцен
    edge_ratio = np.count_nonzero(edges) / (edges.shape[0] * edges.shape[1])
    if edge_ratio < 0.005:
        p90 = float(np.percentile(mag_norm[valid_mask], 90)) if np.any(
            valid_mask) else 128.0
        _, edges_backup = cv2.threshold(mag_norm, p90, 255, cv2.THRESH_BINARY)
        edges = cv2.bitwise_or(edges, edges_backup)
        logger.debug(f"[edges] Резерв p90 (ratio={edge_ratio:.4f})")

    if np.mean(edges > 0) > 0.6:
        p90 = np.percentile(mag_norm[valid_mask], 90) if np.any(
            valid_mask) else 128
        _, edges = cv2.threshold(mag_norm, p90, 255, cv2.THRESH_BINARY)

    return edges, depth_smooth


def _close_edge_gaps(edges: np.ndarray, kernel_size: int, close_iters: int, dilate_iters: int = 1) -> np.ndarray:
    """Морфологическое замыкание разрывов в границах с настраиваемой агрессивностью."""
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    edges = cv2.morphologyEx(edges, cv2.MORPH_DILATE,
                             kernel, iterations=dilate_iters)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE,
                             kernel, iterations=close_iters)
    return edges

def _extract_objects_from_closed_edges(
    edges: np.ndarray,
    min_area: int,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
    depth_work: Optional[NDArray[np.float32]] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    """
    v11: ФИКС для коробки — более консервативный flood-fill + проверка fill_ratio.
    """
    h, w = edges.shape
    inv_raw = cv2.bitwise_not(edges)
    
    # 1. Маска маркёра
    marker_mask = np.zeros((h, w), dtype=np.uint8)
    if marker_bbox is not None:
        mx1, my1, mx2, my2 = marker_bbox
        inv_raw[my1:my2, mx1:mx2] = 0
        marker_mask[my1:my2, mx1:mx2] = 255

    # 🔥 ФИКС: Применяем ROI РАНЬШЕ flood-fill
    if manual_roi is not None:
        rx1, ry1, rx2, ry2 = manual_roi
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(w, rx2), min(h, ry2)
        if rx2 > rx1 and ry2 > ry1:
            # Обнуляем всё вне ROI
            roi_mask = np.zeros_like(inv_raw)
            roi_mask[ry1:ry2, rx1:rx2] = 255
            inv_raw = cv2.bitwise_and(inv_raw, roi_mask)
            logger.info(f"[ROI] Применяем ROI: ({rx1},{ry1})-({rx2},{ry2})")

    # 2. Flood-fill с ЗАЩИЩЁННОЙ копией — работаем на КОПИИ
    inv = inv_raw.copy()
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    
    # 🔥 ФИКС 1: Заливаем ТОЛЬКО если пиксель действительно белый (фон)
    # И используем меньшую связность (4-связность вместо 8-связности по умолчанию)
    for x in range(w):
        if inv[0, x] == 255:
            cv2.floodFill(inv, flood_mask, (x, 0), 0, flags=4)
        if inv[h - 1, x] == 255:
            cv2.floodFill(inv, flood_mask, (x, h - 1), 0, flags=4)
    for y in range(h):
        if inv[y, 0] == 255:
            cv2.floodFill(inv, flood_mask, (0, y), 0, flags=4)
        if inv[y, w - 1] == 255:
            cv2.floodFill(inv, flood_mask, (w - 1, y), 0, flags=4)

    # 3. Connected components на flood-fill-очищенном
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        inv, connectivity=8)

    best_label = -1
    best_score = -1.0

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]

        if area < min_area:
            continue

        # 🔥 ФИКС 2: Более строгий фильтр края (5 пикселей вместо 2)
        margin = 5
        touches_edge = (x <= margin) or (y <= margin) or (
            x + bw >= w - 1 - margin) or (y + bh >= h - 1 - margin)
        if touches_edge:
            continue

        # Фильтр маркёра
        comp_mask = (labels == i).astype(np.uint8) * 255
        inter = cv2.bitwise_and(comp_mask, marker_mask)
        if cv2.countNonZero(inter) > (area * 0.3):
            continue

        # 🔥 ФИКС 3: Проверка fill_ratio — коробка должна быть заполнена плотно
        bbox_area = bw * bh
        fill_ratio = area / bbox_area if bbox_area > 0 else 0
        # Для коробки fill_ratio должен быть > 0.6 (плотное заполнение)
        # Для кусачек допускается > 0.2 (разреженная структура)
        if fill_ratio < 0.6 and area < min_area * 3:
            logger.debug(f"[discontinuity] Компонента {i}: fill_ratio={fill_ratio:.2f} — слишком разреженная")
            continue

        # Score с depth_std и близостью к центру/маркеру
        score = float(area)
        if depth_work is not None:
            obj_depths = depth_work[labels == i]
            if len(obj_depths) > 0:
                depth_std = float(np.std(obj_depths))
                score *= (1.0 + np.clip(depth_std * 30.0, 0.0, 3.0))

        cx_obj = x + bw / 2.0
        cy_obj = y + bh / 2.0
        if marker_bbox is not None:
            cx_m = (marker_bbox[0] + marker_bbox[2]) / 2.0
            cy_m = (marker_bbox[1] + marker_bbox[3]) / 2.0
            dist = np.hypot(cx_obj - cx_m, cy_obj - cy_m)
        else:
            dist = np.hypot(cx_obj - w/2.0, cy_obj - h/2.0)
        score /= (1.0 + dist * 0.003)

        if score > best_score:
            best_score = score
            best_label = i

    # 5. РЕАГРЕГАЦИЯ: если flood-fill уничтожил объект, ищем в inv_raw
    if best_label < 0:
        logger.debug(
            "[discontinuity] Flood-fill уничтожил все объекты, реагрегация из inv_raw...")
        num_labels_raw, labels_raw, stats_raw, _ = cv2.connectedComponentsWithStats(
            inv_raw, connectivity=8)
        for i in range(1, num_labels_raw):
            area = stats_raw[i, cv2.CC_STAT_AREA]
            if area < min_area:
                continue

            x = stats_raw[i, cv2.CC_STAT_LEFT]
            y = stats_raw[i, cv2.CC_STAT_TOP]
            bw = stats_raw[i, cv2.CC_STAT_WIDTH]
            bh = stats_raw[i, cv2.CC_STAT_HEIGHT]

            # Не берём краевые (это фон) и маркёр
            margin = 5  # 🔥 Увеличено до 5
            if (x <= margin) or (y <= margin) or (x + bw >= w - margin) or (y + bh >= h - margin):
                continue

            comp_mask = (labels_raw == i).astype(np.uint8) * 255
            if cv2.bitwise_and(comp_mask, marker_mask).any():
                continue

            # 🔥 ФИКС 4: Проверка fill_ratio для реагрегации
            bbox_area = bw * bh
            fill_ratio = area / bbox_area if bbox_area > 0 else 0

            # Предпочитаем объекты с ненулевой дисперсией глубины (не плоский фон)
            score = float(area)
            if depth_work is not None:
                obj_depths = depth_work[labels_raw == i]
                if len(obj_depths) > 0:
                    depth_std = float(np.std(obj_depths))
                    score *= (1.0 + np.clip(depth_std * 30.0, 0.0, 3.0))

            cx_obj = x + bw / 2.0
            cy_obj = y + bh / 2.0
            if marker_bbox is not None:
                cx_m = (marker_bbox[0] + marker_bbox[2]) / 2.0
                cy_m = (marker_bbox[1] + marker_bbox[3]) / 2.0
                dist = np.hypot(cx_obj - cx_m, cy_obj - cy_m)
            else:
                dist = np.hypot(cx_obj - w/2.0, cy_obj - h/2.0)
            score /= (1.0 + dist * 0.003)

            # 🔥 ФИКС 5: Для коробки требуем fill_ratio > 0.5
            if fill_ratio < 0.5 and area < min_area * 3:
                continue

            if score > best_score:
                best_score = score
                best_label = i
                labels = labels_raw  # переключаемся на raw labels

    if best_label < 0:
        return None

    mask = (labels == best_label).astype(np.uint8) * 255

    # 6. Дополнительная реагрегация: фрагменты рядом с найденным объектом
    # (для кусачек: ручки могли отвалиться в отдельные компоненты)
    if best_label >= 0:
        dilated_main = cv2.dilate(
            mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35)), iterations=1)
        # Ищем в inv_raw (не в inv, т.к. inv уже залит)
        num_labels_raw, labels_raw, stats_raw, _ = cv2.connectedComponentsWithStats(
            inv_raw, connectivity=8)
        for i in range(1, num_labels_raw):
            if i == best_label and labels is labels_raw:
                continue  # уже включён
            area = stats_raw[i, cv2.CC_STAT_AREA]
            if area < max(50, min_area // 10):
                continue

            x = stats_raw[i, cv2.CC_STAT_LEFT]
            y = stats_raw[i, cv2.CC_STAT_TOP]
            bw = stats_raw[i, cv2.CC_STAT_WIDTH]
            bh = stats_raw[i, cv2.CC_STAT_HEIGHT]

            margin = 5  # 🔥 Увеличено
            if (x <= margin) or (y <= margin) or (x + bw >= w - margin) or (y + bh >= h - margin):
                continue

            comp_mask = (labels_raw == i).astype(np.uint8) * 255
            if cv2.bitwise_and(comp_mask, marker_mask).any():
                continue

            if cv2.bitwise_and(comp_mask, dilated_main).any():
                cv2.bitwise_or(mask, comp_mask, dst=mask)

    # 7. Восстановление края у маркёра
    if marker_bbox is not None:
        dilated_mask = cv2.dilate(
            mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        if cv2.bitwise_and(dilated_mask, marker_mask).any():
            mask = cv2.bitwise_or(mask, marker_mask)

    # 8. 🔥 ФИКС 6: Адаптивное восстановление толщины с ПРОВЕРКОЙ fill_ratio
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    
    bx1, by1, bx2, by2 = int(np.min(xs)), int(
        np.min(ys)), int(np.max(xs)) + 1, int(np.max(ys)) + 1
    bbox_area = (bx2 - bx1) * (by2 - by1)
    mask_area = np.count_nonzero(mask)
    fill_ratio = mask_area / bbox_area if bbox_area > 0 else 1.0

    # 🔥 КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ:
    # Для коробки (fill_ratio > 0.6) — минимальное восстановление (3x3, 1 итерация)
    # Для кусачек (fill_ratio < 0.35) — агрессивное восстановление (15x15, 3 итерации)
    # Для всего остального — умеренное (9x9, 2 итерации)
    if fill_ratio < 0.35:
        restore_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        restore_iters = 3
        logger.info(
            f"[discontinuity] Тонкий объект (fill={fill_ratio:.2f}), агрессивное восстановление.")
    elif fill_ratio > 0.6:
        # 🔥 НОВОЕ: для плотных объектов (коробка) почти не восстанавливаем
        restore_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        restore_iters = 1
        logger.info(
            f"[discontinuity] Плотный объект (fill={fill_ratio:.2f}), минимальное восстановление.")
    else:
        restore_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        restore_iters = 2
    
    mask = cv2.dilate(mask, restore_kernel, iterations=restore_iters)

    ys, xs = np.where(mask > 0)
    x = int(np.min(xs))
    y = int(np.min(ys))
    bw = int(np.max(xs) - x + 1)
    bh = int(np.max(ys) - y + 1)
    bbox = (x, y, x + bw, y + bh)

    return bbox, mask.astype(bool)


def measure_bbox_rotated(
    image: NDArray[np.uint8],
    bbox: Tuple[int, int, int, int],
    scale: ScaleEstimator,
    object_mask: Optional[NDArray[np.bool_]] = None,  # ДОБАВЛЕН ПАРАМЕТР
    padding_px: float = 3.0  # 🔥 УМЕНЬШЕНО с 10.0 до 3.0
) -> Dict[str, float]:
    """
    Вычисляет габариты объекта с учётом поворота через minAreaRect.
    v2: Использует точную маску (GrabCut), если она передана.
    """
    x1, y1, x2, y2 = bbox
    rect = None

    # Приоритет: используем точную маску, если она есть
    if object_mask is not None:
        roi_mask = (object_mask[y1:y2, x1:x2]).astype(np.uint8) * 255
        contours, _ = cv2.findContours(
            roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(c)

    # Fallback: старый метод через порог по RGB, если маски нет
    if rect is None:
        roi = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            c = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(c)

    if rect is None:
        return scale.measure_bbox(x1, y1, x2, y2)

    w_px_rot, h_px_rot = rect[1]
    w_px_rot = float(w_px_rot)
    h_px_rot = float(h_px_rot)

    if w_px_rot < h_px_rot:
        w_px_rot, h_px_rot = h_px_rot, w_px_rot

    cx_local, cy_local = rect[0]
    cx_global = x1 + cx_local
    cy_global = y1 + cy_local

    ppm = scale.px_per_m_at_marker

    depth_m: Optional[float] = None
    if scale.depth_map is not None:
        H, W = scale.depth_map.shape
        gx = int(np.clip(cx_global, 0, W - 1))
        gy = int(np.clip(cy_global, 0, H - 1))
        depth_m = float(scale.depth_map[gy, gx])
        ppm = scale.px_per_m_at_depth(depth_m)

    width_m = w_px_rot / ppm
    height_m = h_px_rot / ppm

    box = cv2.boxPoints(rect)
    box[:, 0] += x1
    box[:, 1] += y1
    min_x = float(np.min(box[:, 0]) - padding_px)
    max_x = float(np.max(box[:, 0]) + padding_px)
    min_y = float(np.min(box[:, 1]) - padding_px)
    max_y = float(np.max(box[:, 1]) + padding_px)

    h_img, w_img = image.shape[:2]
    min_x = max(0.0, min_x)
    max_x = min(float(w_img), max_x)
    min_y = max(0.0, min_y)
    max_y = min(float(h_img), max_y)

    return {
        "width_m": width_m,
        "height_m": height_m,
        "width_px": w_px_rot,
        "height_px": h_px_rot,
        "depth_m": depth_m,
        "ppm": ppm,
        "rotated": True,
        "angle_deg": float(rect[2]),
        "viz_bbox": (int(min_x), int(min_y), int(max_x), int(max_y)),
    }


def _refine_mask_with_grabcut(
    image_bgr: NDArray[np.uint8],
    mask: NDArray[np.bool_],
    marker_bbox: Optional[Tuple[int, int, int, int]] = None
) -> NDArray[np.bool_]:
    """
    Уточняет маску объекта с помощью GrabCut на основе RGB-изображения.
    v3: Уменьшена зона поиска для более tight маски.
    """
    h, w = image_bgr.shape[:2]

    # Создаем маску для GrabCut
    gc_mask = np.full((h, w), cv2.GC_BGD, dtype=np.uint8)  # 0 - Всё точный фон

    # 🔥 УМЕНЬШЕНА ЗОНА ПОИСКА: dilate 21x21 вместо 51x51 для более tight маски
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    dilated = cv2.dilate(mask.astype(np.uint8), kernel, iterations=1)
    # 3 - Вероятный объект (где будем искать края)
    gc_mask[dilated == 1] = cv2.GC_PR_FGD

    # Исходная маска от глубины — это точно объект
    gc_mask[mask] = cv2.GC_FGD  # 1 - Точный объект

    # Принудительно указываем маркёр как точный фон
    if marker_bbox is not None:
        mx1, my1, mx2, my2 = marker_bbox
        gc_mask[my1:my2, mx1:mx2] = cv2.GC_BGD

    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(image_bgr, gc_mask, None, bgdModel,
                    fgdModel, 3, cv2.GC_INIT_WITH_MASK)
    except cv2.error as e:
        logger.warning(f"GrabCut failed: {e}. Возврат исходной маски глубины.")
        return mask

    refined_mask = np.where((gc_mask == cv2.GC_FGD) | (
        gc_mask == cv2.GC_PR_FGD), True, False)

    if np.count_nonzero(refined_mask) < 100:
        logger.warning(
            "GrabCut удалил объект. Возврат исходной маски глубины.")
        return mask

    return refined_mask

def _segment_by_depth_deviation(
    depth_work: NDArray[np.float32],
    valid_mask: NDArray[np.bool_],
    min_area: int,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    """
    v10: Фикс порога (60% вместо 40%) + приоритет близости к маркеру.
    """
    h, w = depth_work.shape

    # Оценка фона по периферии
    border = 30
    perim_mask = np.zeros((h, w), dtype=bool)
    perim_mask[:border, :] = True
    perim_mask[-border:, :] = True
    perim_mask[:, :border] = True
    perim_mask[:, -border:] = True
    perim_valid = perim_mask & valid_mask

    if np.count_nonzero(perim_valid) > 100:
        bg_depth = float(np.median(depth_work[perim_valid]))
    else:
        bg_depth = float(np.median(depth_work[valid_mask]))

    # Порог: 3% от глубины фона, минимум 2 см
    thresh = max(bg_depth * 0.03, 0.02)
    diff = np.abs(depth_work.astype(np.float32) - bg_depth)
    obj_mask = ((diff > thresh) & valid_mask).astype(np.uint8) * 255

    # Порог отказа: 60% (коробка занимает ~40-50% кадра)
    obj_ratio = np.count_nonzero(obj_mask) / (h * w)
    if obj_ratio > 0.60:
        logger.warning(f"[deviation] Слишком много пикселей ({obj_ratio:.1%})")
        return None

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    obj_mask = cv2.morphologyEx(
        obj_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    obj_mask = cv2.morphologyEx(obj_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    if marker_bbox is not None:
        mx1, my1, mx2, my2 = marker_bbox
        obj_mask[my1:my2, mx1:mx2] = 0

    if manual_roi is not None:
        rx1, ry1, rx2, ry2 = manual_roi
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(w, rx2), min(h, ry2)
        if rx2 > rx1 and ry2 > ry1:
            roi_mask = np.zeros_like(obj_mask)
            roi_mask[ry1:ry2, rx1:rx2] = 255
            obj_mask = cv2.bitwise_and(obj_mask, roi_mask)

    contours, _ = cv2.findContours(
        obj_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    marker_mask = np.zeros((h, w), dtype=np.uint8)
    if marker_bbox is not None:
        mx1, my1, mx2, my2 = marker_bbox
        marker_mask[my1:my2, mx1:mx2] = 255

    best_contour = None
    best_score = -1.0

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue

        temp_mask = np.zeros_like(obj_mask)
        cv2.drawContours(temp_mask, [c], -1, 255, thickness=cv2.FILLED)
        inter = cv2.bitwise_and(temp_mask, marker_mask)
        if cv2.countNonZero(inter) > (area * 0.3):
            continue

        x, y, bw, bh = cv2.boundingRect(c)
        aspect = min(bw, bh) / max(bw, bh) if max(bw, bh) > 0 else 1.0

        # Приоритет близости к маркеру
        cx_obj = x + bw / 2.0
        cy_obj = y + bh / 2.0
        if marker_bbox is not None:
            cx_m = (marker_bbox[0] + marker_bbox[2]) / 2.0
            cy_m = (marker_bbox[1] + marker_bbox[3]) / 2.0
            dist_to_marker = np.hypot(cx_obj - cx_m, cy_obj - cy_m)
        else:
            dist_to_marker = np.hypot(cx_obj - w/2.0, cy_obj - h/2.0)

        # Score: area / distance, штраф за квадратный мелкий мусор
        score = area / (1.0 + dist_to_marker * 0.005)
        if area < min_area * 2 and aspect > 0.7:
            score *= 0.3

        if score > best_score:
            best_score = score
            best_contour = c

    if best_contour is None:
        return None

    mask = np.zeros_like(obj_mask, dtype=np.uint8)
    cv2.drawContours(mask, [best_contour], -1, 255, thickness=cv2.FILLED)

    # Адаптивное восстановление толщины
    ys, xs = np.where(mask > 0)
    bx1, by1, bx2, by2 = int(np.min(xs)), int(
        np.min(ys)), int(np.max(xs)) + 1, int(np.max(ys)) + 1
    bbox_area = (bx2 - bx1) * (by2 - by1)
    mask_area = np.count_nonzero(mask)
    fill_ratio = mask_area / bbox_area if bbox_area > 0 else 1.0

    if fill_ratio < 0.35:
        restore_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        restore_iters = 3
    else:
        restore_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        restore_iters = 2

    mask = cv2.dilate(mask, restore_kernel, iterations=restore_iters)

    ys, xs = np.where(mask > 0)
    x = int(np.min(xs))
    y = int(np.min(ys))
    bw = int(np.max(xs) - x + 1)
    bh = int(np.max(ys) - y + 1)
    bbox = (x, y, x + bw, y + bh)

    logger.info(f"[deviation] Успех, bbox={bbox}")
    return bbox, mask.astype(bool)


def _segment_by_discontinuity(
    depth_work: NDArray[np.float32],
    valid_mask: NDArray[np.bool_],
    min_area: int,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    """
    v10: Гибридный пайплайн.
    """
    edges, depth_smooth = _build_edges_from_depth(depth_work, valid_mask)

    if cv2.countNonZero(edges) == 0:
        logger.info("[discontinuity] Нет edges, пробуем девиацию...")
        return _segment_by_depth_deviation(depth_work, valid_mask, min_area, manual_roi, marker_bbox)

    levels = [
        (7, 3, 1, "standard"),
        (9, 5, 2, "aggressive"),
        (15, 7, 3, "heavy"),
    ]

    for ksize, close_it, dilate_it, name in levels:
        edges_closed = _close_edge_gaps(edges, ksize, close_it, dilate_it)
        result = _extract_objects_from_closed_edges(
            edges_closed, min_area, manual_roi, marker_bbox, depth_work)
        if result is not None:
            logger.info(f"[discontinuity] Успех ({name}), bbox={result[0]}")
            return result
        logger.debug(f"[discontinuity] Уровень {name} не дал объектов.")

    logger.info("[discontinuity] Границы не замкнулись, пробуем девиацию...")
    return _segment_by_depth_deviation(depth_work, valid_mask, min_area, manual_roi, marker_bbox)


def _segment_by_otsu(
    depth_work: NDArray[np.float32],
    valid_mask: NDArray[np.bool_],
    min_area: int,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    width: int = 0,
    height: int = 0,
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    depth_valid = depth_work[valid_mask]
    depth_norm = np.zeros_like(depth_work)
    depth_range = depth_valid.max() - depth_valid.min() + 1e-5
    depth_norm[valid_mask] = (depth_valid - depth_valid.min()) / depth_range

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

    # 🔥 ОБЯЗАТЕЛЬНО: Убираем баг, при котором NaN-маркер становится белым пятном
    marker_mask = np.zeros_like(binary, dtype=np.uint8)
    if marker_bbox is not None:
        mx1, my1, mx2, my2 = marker_bbox
        binary[my1:my2, mx1:mx2] = 0
        marker_mask[my1:my2, mx1:mx2] = 255

    if manual_roi is not None:
        rx1, ry1, rx2, ry2 = manual_roi
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(width, rx2), min(height, ry2)
        if rx2 > rx1 and ry2 > ry1:
            roi_mask = np.zeros_like(binary)
            roi_mask[ry1:ry2, rx1:rx2] = 255
            binary = cv2.bitwise_and(binary, roi_mask)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    if not valid_contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < min_area * 0.5:
            return None
    else:
        largest_contour = max(valid_contours, key=cv2.contourArea)

    mask = np.zeros_like(binary, dtype=np.uint8)
    cv2.drawContours(mask, [largest_contour], -1, 255, thickness=cv2.FILLED)

    # 🔥 ВОССТАНОВЛЕНИЕ ОБРЕЗАННОГО КРАЯ (СКЛЕЙКА)
    if marker_bbox is not None:
        dilated_mask = cv2.dilate(
            mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
        if cv2.bitwise_and(dilated_mask, marker_mask).any():
            mask = cv2.bitwise_or(mask, marker_mask)

    x, y, w, h = cv2.boundingRect(largest_contour)
    bbox = (x, y, x + w, y + h)

    return bbox, mask.astype(bool)


def _refine_mask_with_grabcut(
    image_bgr: NDArray[np.uint8],
    mask: NDArray[np.bool_],
    marker_bbox: Optional[Tuple[int, int, int, int]] = None
) -> NDArray[np.bool_]:
    """
    Уточняет маску объекта с помощью GrabCut на основе RGB-изображения.
    v2: Увеличена зона вероятного объекта для захвата тонких кончиков (кусачек).
    """
    h, w = image_bgr.shape[:2]

    # Создаем маску для GrabCut
    gc_mask = np.full((h, w), cv2.GC_BGD, dtype=np.uint8)  # 0 - Всё точный фон

    # 🔥 УВЕЛИЧЕНА ЗОНА ПОИСКА: dilate 51x51 вместо 31x31
    # Это позволяет GrabCut "дотянуться" до кончиков кусачек, даже если глубина их не видела
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    dilated = cv2.dilate(mask.astype(np.uint8), kernel, iterations=1)
    # 3 - Вероятный объект (где будем искать края)
    gc_mask[dilated == 1] = cv2.GC_PR_FGD

    # Исходная маска от глубины — это точно объект
    gc_mask[mask] = cv2.GC_FGD  # 1 - Точный объект

    # Принудительно указываем маркёр как точный фон
    if marker_bbox is not None:
        mx1, my1, mx2, my2 = marker_bbox
        gc_mask[my1:my2, mx1:mx2] = cv2.GC_BGD

    bgdModel = np.zeros((1, 65), np.float64)
    fgdModel = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(image_bgr, gc_mask, None, bgdModel,
                    fgdModel, 3, cv2.GC_INIT_WITH_MASK)
    except cv2.error as e:
        logger.warning(f"GrabCut failed: {e}. Возврат исходной маски глубины.")
        return mask

    refined_mask = np.where((gc_mask == cv2.GC_FGD) | (
        gc_mask == cv2.GC_PR_FGD), True, False)

    if np.count_nonzero(refined_mask) < 100:
        logger.warning(
            "GrabCut удалил объект. Возврат исходной маски глубины.")
        return mask

    return refined_mask

def segment_object_from_depth(
    depth_map: NDArray[np.float32],
    image_bgr: NDArray[np.uint8],
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
    min_object_area_ratio: float = 0.02,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    method: str = "discontinuity",
) -> Optional[Tuple[Tuple[int, int, int, int], NDArray[np.bool_]]]:
    """
    Автоматически сегментирует объект из карты глубины.
    """
    height, width = depth_map.shape
    marker_bbox_xyxy = None
    if marker_bbox is not None:
        bx, by, bw, bh = marker_bbox
        marker_bbox_xyxy = (bx, by, bx + bw, by + bh)

    depth_work = depth_map.copy()
    if marker_bbox_xyxy is not None:
        x1, y1, x2, y2 = marker_bbox_xyxy
        depth_work[y1:y2, x1:x2] = np.nan

    valid_mask = (~np.isnan(depth_work) & (
        depth_work > 0.1) & (depth_work < 10.0))
    if valid_mask.sum() < 100:
        return None

    min_area = int(height * width * min_object_area_ratio)

    # Попытка 1: Depth Discontinuity
    if method == "discontinuity":
        result = _segment_by_discontinuity(
            depth_work, valid_mask, min_area, manual_roi, marker_bbox_xyxy)
        if result is not None:
            bbox, mask = result
            # 🔥 ИСПРАВЛЕНИЕ: Увеличиваем порог с 30% до 70% для top view
            # Для вида сверху объект legitimately занимает большую часть кадра
            bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            image_area = height * width
            coverage = bbox_area / image_area
            
            # Для top view допускаем до 70% покрытия кадра
            # Для front/side view оставляем 40%
            max_coverage = 0.70  # Увеличено с 0.30 до 0.70
            
            if coverage > max_coverage:
                logger.warning(
                    f"[discontinuity] Bbox слишком большой ({coverage:.1%} кадра), "
                    f"пробуем Otsu..."
                )
            else:
                logger.info(f"[discontinuity] Принят bbox с покрытием {coverage:.1%}")
                return result

    # Попытка 2: Otsu
    seg_result = _segment_by_otsu(
        depth_work, valid_mask, min_area, manual_roi, width, height, marker_bbox_xyxy)
    
    if seg_result is not None:
        bbox, mask = seg_result
        # Валидация для Otsu
        bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        image_area = height * width
        coverage = bbox_area / image_area
        
        # 🔥 ИСПРАВЛЕНИЕ: Увеличиваем порог для Otsu с 30% до 70%
        if coverage > 0.70:  # Увеличено с 0.30 до 0.70
            logger.warning(
                f"[otsu] Bbox слишком большой ({coverage:.1%} кадра), "
                f"возвращаем None для fallback"
            )
            return None
        
        logger.info(f"[otsu] Принят bbox с покрытием {coverage:.1%}")
        logger.info("Уточнение маски объекта через GrabCut (RGB-контуры)...")
        mask = _refine_mask_with_grabcut(image_bgr, mask, marker_bbox_xyxy)
        
        ys, xs = np.where(mask)
        if len(xs) == 0:
            return None
        x = int(np.min(xs))
        y = int(np.min(ys))
        bw = int(np.max(xs) - x + 1)
        bh = int(np.max(ys) - y + 1)
        bbox = (x, y, x + bw, y + bh)
        return bbox, mask
    
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 6. Визуализация и API
# ─────────────────────────────────────────────────────────────────────────────


def draw_marker(image, corners, marker_id, marker_size_m):
    pts = corners.astype(int)
    cv2.polylines(image, [pts], isClosed=True, color=COLOR_MARKER, thickness=2)
    cx, cy = marker_center(corners)
    label = f"ArUco ID={marker_id} [{marker_size_m*1000:.1f}mm]"
    cv2.putText(image, label, (int(cx)-50, int(cy)-50),
                FONT, 0.6, COLOR_MARKER, 2)


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
    segmentation_method: str = "discontinuity",
    fallback_dimensions: Optional[Dict[str, float]] = None,
) -> Tuple[Optional[Dict[str, float]], NDArray[np.uint8], Optional[NDArray[np.bool_]]]:
    """Полностью автоматический конвейер измерения габаритов."""
    result_img = image_bgr.copy()
    
    # 1. Маркёр
    corners, marker_id, _ = detect_aruco(
        image_bgr, aruco_dict, expected_marker_id)
    if corners is None:
        return None, result_img, None

    marker_bbox_cv = cv2.boundingRect(corners.astype(np.float32))
    marker_bbox = tuple(marker_bbox_cv)
    draw_marker(result_img, corners, marker_id, marker_size_m)

    # 2. Масштаб
    scale = ScaleEstimator(corners, marker_size_m, depth_map, same_plane=same_plane)

    # 3. Сегментация
    seg_result = segment_object_from_depth(
        depth_map, image_bgr, marker_bbox=marker_bbox, manual_roi=manual_roi,
        method=segmentation_method,
    )
    
    if seg_result is None:
        # Fallback: если есть предвычисленные размеры (например, из front/side)
        if fallback_dimensions is not None:
            logger.info(f"[{object_label}] Используем fallback размеры: {fallback_dimensions}")
            return {
                "width_m": fallback_dimensions.get("width_mm", 0) / 1000.0,
                "height_m": fallback_dimensions.get("height_mm", 0) / 1000.0,
                "width_px": 0,
                "height_px": 0,
                "depth_m": 0,
                "ppm": scale.px_per_m_at_marker,
                "rotated": False,
                "angle_deg": 0,
                "viz_bbox": (0, 0, 0, 0),
            }, result_img, None
        return None, result_img, None

    bbox, object_mask = seg_result

    # 4. Измерение с учётом поворота
    measurements = measure_bbox_rotated(
        result_img, bbox, scale, object_mask)

    viz_bbox = measurements.get("viz_bbox", bbox)
    draw_measurement(result_img, viz_bbox[0], viz_bbox[1],
                     viz_bbox[2], viz_bbox[3], measurements, object_label)
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
    segmentation_method: str = "discontinuity",
) -> Tuple[Optional[Dict[str, float]], NDArray[np.uint8], NDArray[np.uint8]]:
    """Конвейер измерения с использованием обёртки глубинной модели."""
    logger.info("Запуск Depth Anything V2 (metric depth)...")
    depth_map = wrapper.estimate(image_bgr, multi_scale=multi_scale)

    # Визуализация глубины
    depth_vis = wrapper.estimate_visual(
        image_bgr, normalize="metric_range", multi_scale=multi_scale)

    # Автоматическое измерение
    measurements, annotated, object_mask = measure_object_auto(
        image_bgr,
        marker_size_m=marker_size_m,
        depth_map=depth_map,
        object_label=object_label,
        same_plane=same_plane,
        manual_roi=manual_roi,
        expected_marker_id=expected_marker_id,
        segmentation_method=segmentation_method,
    )
    return measurements, annotated, depth_vis
