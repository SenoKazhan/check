"""
aruco_measure.py
================
Модуль измерения габаритов объектов по 2D-изображениям с использованием ArUco-маркера
и монокулярной оценки глубины.

"Зона исключения" (Exclusion Mask) для маркёра
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, List

import cv2
import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


def _debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[Dict] = None,
    run_id: str = "initial",
) -> None:
    payload = {
        "sessionId": "d10f19",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(__import__("time").time() * 1000),
    }
    try:
        with open(r"C:\Users\kayax\.cursor\projects\empty-window\debug-d10f19.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass

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

# Add AprilTag dictionaries when available in current OpenCV build.
for _name in ("DICT_APRILTAG_16h5", "DICT_APRILTAG_25h9", "DICT_APRILTAG_36h10", "DICT_APRILTAG_36h11"):
    if hasattr(cv2.aruco, _name):
        ARUCO_DICTS.append((_name.replace("DICT_", ""), getattr(cv2.aruco, _name)))

FONT      = cv2.FONT_HERSHEY_SIMPLEX
COLOR_MRK = (0, 255, 0)    # маркёр — зелёный
COLOR_OBJ = (255, 100, 0)  # объект — синий/оранжевый
COLOR_TXT = (255, 255, 255)
COLOR_BG  = (30, 30, 30)



import cv2
import numpy as np
from typing import Optional, Tuple


def segment_object_in_roi(
    depth_map: np.ndarray,
    image_bgr: np.ndarray,
    roi: Tuple[int, int, int, int],
    depth_tolerance: float = 0.08,
    use_grabcut: bool = True,
):
    """
    Сегментация объекта внутри ROI через:
    - local depth
    - connected component
    - optional GrabCut refinement

    roi = (x1, y1, x2, y2)
    """

    x1, y1, x2, y2 = roi

    roi_depth = depth_map[y1:y2, x1:x2].copy()
    roi_rgb = image_bgr[y1:y2, x1:x2].copy()

    H, W = roi_depth.shape

    # ---------------------------------------------------
    # 1. seed depth из центра ROI
    # ---------------------------------------------------

    cx = W // 2
    cy = H // 2

    patch = 7

    px1 = max(0, cx - patch)
    px2 = min(W, cx + patch)

    py1 = max(0, cy - patch)
    py2 = min(H, cy + patch)

    center_patch = roi_depth[py1:py2, px1:px2]

    valid = center_patch[~np.isnan(center_patch)]

    if valid.size == 0:
        return None

    seed_depth = np.median(valid)

    # ---------------------------------------------------
    # 2. depth similarity
    # ---------------------------------------------------

    depth_mask = np.abs(roi_depth - seed_depth) < depth_tolerance

    depth_mask = depth_mask.astype(np.uint8) * 255

    # ---------------------------------------------------
    # 3. morphology (очень слабая)
    # ---------------------------------------------------

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (3, 3)
    )

    depth_mask = cv2.morphologyEx(
        depth_mask,
        cv2.MORPH_OPEN,
        kernel,
        iterations=1
    )

    # ---------------------------------------------------
    # 4. connected component от центра
    # ---------------------------------------------------

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        depth_mask,
        connectivity=8
    )

    center_label = labels[cy, cx]

    if center_label == 0:
        return None

    object_mask = (labels == center_label).astype(np.uint8)

    # ---------------------------------------------------
    # 5. optional GrabCut refine
    # ---------------------------------------------------

    if use_grabcut:

        gc_mask = np.where(
            object_mask == 1,
            cv2.GC_PR_FGD,
            cv2.GC_BGD
        ).astype("uint8")

        bgdModel = np.zeros((1, 65), np.float64)
        fgdModel = np.zeros((1, 65), np.float64)

        cv2.grabCut(
            roi_rgb,
            gc_mask,
            None,
            bgdModel,
            fgdModel,
            3,
            cv2.GC_INIT_WITH_MASK
        )

        object_mask = np.where(
            (gc_mask == cv2.GC_FGD) |
            (gc_mask == cv2.GC_PR_FGD),
            1,
            0
        ).astype(np.uint8)

    # ---------------------------------------------------
    # 6. bbox
    # ---------------------------------------------------

    ys, xs = np.where(object_mask > 0)

    if len(xs) == 0:
        return None

    bx1 = xs.min()
    by1 = ys.min()

    bx2 = xs.max()
    by2 = ys.max()

    # глобальные координаты

    gx1 = x1 + bx1
    gy1 = y1 + by1

    gx2 = x1 + bx2
    gy2 = y1 + by2

    full_mask = np.zeros_like(depth_map, dtype=np.uint8)

    full_mask[y1:y2, x1:x2] = object_mask * 255

    return (
        (gx1, gy1, gx2, gy2),
        full_mask.astype(bool)
    )
    
# ─────────────────────────────────────────────────────────────────────────────
# 1. Детекция ArUco с субпиксельной точностью
# ─────────────────────────────────────────────────────────────────────────────

def detect_aruco(
    image_bgr: np.ndarray,
    target_dict: Optional[str] = None,
    expected_marker_id: Optional[int] = None,
) -> Tuple[Optional[np.ndarray], Optional[int], Optional[str]]:
    """
    Ищет ArUco-маркёр с расширенными параметрами детекции.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    
    # Пробуем разные словари
    dicts_to_try = ARUCO_DICTS
    if target_dict:
        dicts_to_try = [(n, d) for n, d in ARUCO_DICTS if target_dict.upper() in n]

    # Пробуем несколько вариантов обработки изображения
    variants = [
        ("original", gray),
        ("equalized", cv2.equalizeHist(gray)),
        ("blurred", cv2.GaussianBlur(gray, (5, 5), 0)),
    ]
    
    for name, dict_id in dicts_to_try:
        aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        
        # Пробуем разные наборы параметров
        param_sets = [
            # Стандартные
            {
                "adaptiveThreshWinSizeMin": 3,
                "adaptiveThreshWinSizeMax": 53,
                "minMarkerPerimeterRate": 0.03,
                "maxMarkerPerimeterRate": 4.0,
                "polygonalApproxAccuracyRate": 0.03,
                "cornerRefinementMethod": cv2.aruco.CORNER_REFINE_SUBPIX,
            },
            # Более мягкие (для сложных условий)
            {
                "adaptiveThreshWinSizeMin": 5,
                "adaptiveThreshWinSizeMax": 103,
                "minMarkerPerimeterRate": 0.01,  # Меньше порог
                "maxMarkerPerimeterRate": 10.0,   # Больше порог
                "polygonalApproxAccuracyRate": 0.1,  # Менее строгая
                "minCornerDistanceRate": 0.05,
                "minDistanceToBorder": 1,  # Меньше отступ от края
                "cornerRefinementMethod": cv2.aruco.CORNER_REFINE_SUBPIX,
            },
        ]
        
        for variant_name, gray_variant in variants:
            for i, params_dict in enumerate(param_sets):
                params = cv2.aruco.DetectorParameters()
                for key, value in params_dict.items():
                    setattr(params, key, value)
                
                detector = cv2.aruco.ArucoDetector(aruco_dict, params)
                corners_list, ids, rejected = detector.detectMarkers(gray_variant)
                
                if ids is not None and len(ids) > 0:
                    for j in range(len(ids)):
                        c = corners_list[j][0].astype(np.float32)
                        marker_id = int(ids[j][0])
                        
                        # Субпиксельное уточнение
                        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                        corners = cv2.cornerSubPix(
                            gray_variant, c, (11, 11), (-1, -1), criteria
                        )
                        
                        if expected_marker_id is not None and marker_id != expected_marker_id:
                            continue
                            
                        logger.info(f"✅ ArUco найден: словарь={name}, variant={variant_name}, params_set={i}, ID={marker_id}")
                        return corners, marker_id, name
    
    logger.warning("❌ ArUco-маркёр не найден ни в одном словаре")
    return None, None, None


def marker_side_px(corners: np.ndarray) -> float:
    sides = [np.linalg.norm(corners[i] - corners[(i + 1) % 4]) for i in range(4)]
    return float(np.mean(sides))


def marker_center(corners: np.ndarray) -> Tuple[float, float]:
    return float(corners[:, 0].mean()), float(corners[:, 1].mean())


# ─────────────────────────────────────────────────────────────────────────────
# 2. Масштаб и измерение
# ─────────────────────────────────────────────────────────────────────────────

class ScaleEstimator:
    def __init__(
        self,
        corners: np.ndarray,
        marker_size_m: float,
        depth_map: Optional[np.ndarray] = None,
        same_plane: bool = True,
    ):
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

        self.px_per_m_at_marker = self._side_px / marker_size_m

        logger.info(
            f"Масштаб: {self._side_px:.2f} px / {marker_size_m*1000:.1f} mm "
            f"= {self.px_per_m_at_marker:.1f} px/m"
        )

    def px_per_m_at_depth(self, depth_m: float) -> float:
        if self.same_plane or self.marker_depth_m is None or self.marker_depth_m < 0.01:
            return self.px_per_m_at_marker
        ratio = self.marker_depth_m / depth_m
        ratio = np.clip(ratio, 0.90, 1.10)
        return self.px_per_m_at_marker * ratio

    def measure_bbox(
        self,
        x1: int, y1: int, x2: int, y2: int,
    ) -> Dict[str, float]:
        w_px = abs(x2 - x1)
        h_px = abs(y2 - y1)
        
        if self.depth_map is not None:
            H, W = self.depth_map.shape
            rx0, ry0 = int(np.clip(x1, 0, W-1)), int(np.clip(y1, 0, H-1))
            rx1, ry1 = int(np.clip(x2, 0, W-1)), int(np.clip(y2, 0, H-1))
            roi = self.depth_map[ry0:ry1, rx0:rx1]
            obj_depth_m = float(np.percentile(roi, 10)) if roi.size > 0 else self.marker_depth_m
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
    scale: 'ScaleEstimator',
    padding_px: float = 10.0
) -> Dict[str, float]:
    """
    Измеряет объект с коррекцией перспективы для длинных объектов.
    """
    x1, y1, x2, y2 = bbox
    roi = image[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return scale.measure_bbox(x1, y1, x2, y2)
    
    c = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(c)
    (center), (size_width, size_height), angle = rect
    
    box = cv2.boxPoints(rect)
    box = np.int0(box)
    
    min_x = np.min(box[:, 0])
    max_x = np.max(box[:, 0])
    min_y = np.min(box[:, 1])
    max_y = np.max(box[:, 1])
    
    # 🔥 КОРРЕКЦИЯ ПЕРСПЕКТИВЫ для длинных объектов
    if scale.depth_map is not None:
        H, W = scale.depth_map.shape
        gx1, gy1 = x1 + int(min_x), y1 + int(min_y)
        gx2, gy2 = x1 + int(max_x), y1 + int(max_y)
        
        # Извлекаем глубину в области объекта
        roi_depth = scale.depth_map[gy1:gy2, gx1:gx2]
        valid_depth = roi_depth[~np.isnan(roi_depth)]
        
        if len(valid_depth) > 100:  # Достаточно данных
            # Проверяем градиент глубины
            depth_std = np.std(valid_depth)
            depth_mean = np.median(valid_depth)
            depth_range = depth_max - depth_min if (depth_max := np.max(valid_depth)) - (depth_min := np.min(valid_depth)) > 0 else 0
            
            # Если разброс глубины > 5% — применяем коррекцию
            if depth_std / depth_mean > 0.05:
                logger.info(f"[PERSPECTIVE] Градиент глубины: {depth_std/depth_mean*100:.1f}%")
                
                # Разбиваем bbox на части и вычисляем локальный масштаб
                w_roi = gx2 - gx1
                h_roi = gy2 - gy1
                
                # Левая и правая части
                left_depth = np.median(roi_depth[:, :w_roi//3][~np.isnan(roi_depth[:, :w_roi//3])])
                right_depth = np.median(roi_depth[:, -w_roi//3:][~np.isnan(roi_depth[:, -w_roi//3:])])
                
                if not np.isnan(left_depth) and not np.isnan(right_depth):
                    # Локальный масштаб для каждой части
                    scale_left = scale.px_per_m_at_marker * (scale.marker_depth_m / left_depth)
                    scale_right = scale.px_per_m_at_marker * (scale.marker_depth_m / right_depth)
                    
                    # Средний масштаб с учётом перспективы
                    avg_scale = (scale_left + scale_right) / 2
                    logger.info(f"[PERSPECTIVE] Масштаб: слева={scale_left:.1f}, справа={scale_right:.1f}, средний={avg_scale:.1f}")
                    
                    ppm = avg_scale
                else:
                    ppm = scale.px_per_m_at_marker
            else:
                ppm = scale.px_per_m_at_marker
        else:
            ppm = scale.px_per_m_at_marker
    else:
        ppm = scale.px_per_m_at_marker
    
    w_px = max_x - min_x
    h_px = max_y - min_y
    
    width_m = w_px / ppm
    height_m = h_px / ppm
    
    # Глубина
    depth_m = None
    if scale.depth_map is not None:
        gx1, gy1 = x1 + int(min_x), y1 + int(min_y)
        gx2, gy2 = x1 + int(max_x), y1 + int(max_y)
        H, W = scale.depth_map.shape
        rx0, ry0 = int(np.clip(gx1, 0, W-1)), int(np.clip(gy1, 0, H-1))
        rx1, ry1 = int(np.clip(gx2, 0, W-1)), int(np.clip(gy2, 0, H-1))
        roi_depth = scale.depth_map[ry0:ry1, rx0:rx1]
        depth_m = float(np.percentile(roi_depth[~np.isnan(roi_depth)], 10)) if roi_depth.size > 0 else None
    
    # Padding
    h_roi, w_roi = roi.shape[:2]
    min_x = max(0, min_x - padding_px)
    max_x = min(w_roi, max_x + padding_px)
    min_y = max(0, min_y - padding_px)
    max_y = min(h_roi, max_y + padding_px)
    
    return {
        "width_m": width_m,
        "height_m": height_m,
        "width_px": max_x - min_x,
        "height_px": max_y - min_y,
        "depth_m": depth_m,
        "ppm": ppm,
        "rotated": True,
        "perspective_corrected": True if scale.depth_map is not None else False
    }

# ─────────────────────────────────────────────────────────────────────────────
# 3. Автоматическая сегментация с ИГНОРИРОВАНИЕМ маркёра
# ─────────────────────────────────────────────────────────────────────────────

def segment_object_from_depth(
    depth_map: np.ndarray,
    image_bgr: np.ndarray,
    marker_bbox: Optional[Tuple[int, int, int, int]] = None,
    min_object_area_ratio: float = 0.02,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Tuple[Tuple[int, int, int, int], np.ndarray]]:
    """
    Сегментация с подробным дебагом и контролируемой вертикальной дилатацией.
    """
    H, W = depth_map.shape
    total_pixels = H * W
    
    # 1. Копия + исключение маркёра
    depth_work = depth_map.copy()
    if marker_bbox:
        mx, my, mw, mh = marker_bbox
        depth_work[my:my+mh, mx:mx+mw] = np.nan  

    # 2. Валидные пиксели
    valid_mask = ~np.isnan(depth_work) & (depth_work > 1.5) & (depth_work < 5.75)
    if valid_mask.sum() < 500:
        return None
    
    depth_valid = depth_work[valid_mask]
    d_min, d_max = depth_valid.min(), depth_valid.max()
    if d_max - d_min < 1e-5:
        return None

    # 3. Нормализация
    depth_scaled = np.zeros_like(depth_work, dtype=np.uint8)
    depth_scaled[valid_mask] = ((depth_work[valid_mask] - d_min) / (d_max - d_min + 1e-5) * 255).astype(np.uint8)

    # 4. Порог 20-го перцентиля
    thresh_val = np.percentile(depth_scaled[valid_mask], 20)
    _, binary = cv2.threshold(
        depth_scaled, 
        int(thresh_val), 
        255, 
        cv2.THRESH_BINARY_INV
    )
    logger.info(f"[DEBUG] Порог: {thresh_val:.1f}/255, белых пикселей: {cv2.countNonZero(binary)}")
    cv2.imwrite("debug_01_threshold.png", binary)

    # 5. Исключение маркёра
    if marker_bbox:
        exclusion_mask = np.ones_like(binary, dtype=np.uint8) * 255
        mx, my, mw, mh = marker_bbox
        padding = 15 
        x1, y1 = max(0, mx - padding), max(0, my - padding)
        x2, y2 = min(W, mx + mw + padding), min(H, my + mh + padding)
        exclusion_mask[y1:y2, x1:x2] = 0
        binary = cv2.bitwise_and(binary, binary, mask=exclusion_mask)
        logger.info(f"[DEBUG] После исключения маркёра: {cv2.countNonZero(binary)} px")
        cv2.imwrite("debug_02_exclusion.png", binary)

    # 5.1 Принудительное ограничение по ручному ROI (если задан)
    if manual_roi is not None:
        rx1, ry1, rx2, ry2 = manual_roi
        rx1 = max(0, min(W - 1, int(rx1)))
        ry1 = max(0, min(H - 1, int(ry1)))
        rx2 = max(0, min(W, int(rx2)))
        ry2 = max(0, min(H, int(ry2)))
        if rx2 > rx1 and ry2 > ry1:
            roi_mask = np.zeros_like(binary, dtype=np.uint8)
            roi_mask[ry1:ry2, rx1:rx2] = 255
            binary = cv2.bitwise_and(binary, binary, mask=roi_mask)

    # 6. Морфология с поэтапным дебагом
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    logger.info(f"[DEBUG] После CLOSE: {cv2.countNonZero(binary)} px")
    cv2.imwrite("debug_03_close.png", binary)
    
    
    # Лёгкая общая дилатация
    binary = cv2.dilate(binary, kernel, iterations=1)
    logger.info(f"[DEBUG] После финальной дилатации: {cv2.countNonZero(binary)} px")
    cv2.imwrite("debug_05_final_binary.png", binary)

    # 7. Поиск контуров с анализом
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # Анализируем все контуры
    contour_info = []
    for i, c in enumerate(contours):
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        contour_info.append({
            'index': i,
            'area': area,
            'bbox': (x, y, w, h),
            'aspect_ratio': w/h if h > 0 else 0
        })
    
    # Сортируем по площади
    contour_info.sort(key=lambda x: x['area'], reverse=True)
    
    logger.info(f"[DEBUG] Найдено {len(contours)} контуров:")
    for info in contour_info[:5]:  # Показываем топ-5
        logger.info(f"  Контур {info['index']}: площадь={info['area']:.0f}, bbox={info['bbox']}, AR={info['aspect_ratio']:.2f}")
    
    min_area = total_pixels * min_object_area_ratio
    
    # Берём крупнейший контур, который больше порога
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    
    if not valid_contours:
        logger.warning(f"[DEBUG] Нет контуров > {min_area:.0f} px. Берём крупнейший.")
        largest_contour = max(contours, key=cv2.contourArea)
    else:
        if manual_roi is not None:
            rx1, ry1, rx2, ry2 = manual_roi
            roi_pref = []
            for c in valid_contours:
                x, y, w, h = cv2.boundingRect(c)
                ix1, iy1 = max(x, rx1), max(y, ry1)
                ix2, iy2 = min(x + w, rx2), min(y + h, ry2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                roi_pref.append((inter, cv2.contourArea(c), c))
            roi_pref.sort(key=lambda t: (t[0], t[1]), reverse=True)
            largest_contour = roi_pref[0][2]
        else:
            largest_contour = max(valid_contours, key=cv2.contourArea)

    x, y, w, h = cv2.boundingRect(largest_contour)
    bbox = (x, y, x + w, y + h)
    
    mask = np.zeros_like(binary)
    cv2.drawContours(mask, [largest_contour], -1, 255, -1)
    
    logger.info(f"[DEBUG] Итоговый bbox: {bbox}, площадь={cv2.countNonZero(mask)} px")
    logger.info(f"[DEBUG] Отношение сторон: {w/h:.2f}")
    cv2.imwrite("debug_06_final_mask.png", mask)
    
    return bbox, mask.astype(bool)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Визуализация
# ─────────────────────────────────────────────────────────────────────────────

def enhance_depth_visualization(
    depth_map: np.ndarray,
    bbox: Optional[Tuple[int, int, int, int]] = None,
    gamma: float = 0.75,
    colormap: int = cv2.COLORMAP_VIRIDIS
) -> np.ndarray:
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
    
    depth_norm = np.power(depth_norm, 1.0 / gamma)
    depth_u8 = (depth_norm * 255).astype(np.uint8)
    depth_vis = cv2.applyColorMap(depth_u8, colormap)
    
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(depth_vis, (x1, y1), (x2, y2), (255, 255, 255), 2)
    
    return depth_vis


def draw_marker(image: np.ndarray, corners: np.ndarray, marker_id: int, marker_size_m: float) -> None:
    pts = corners.astype(int)
    cv2.polylines(image, [pts], isClosed=True, color=COLOR_MRK, thickness=2)
    for pt in pts:
        cv2.circle(image, tuple(pt), 5, COLOR_MRK, -1)
    cx, cy = marker_center(corners)
    label = f"ArUco ID={marker_id} [{marker_size_m*1000:.1f}mm]"
    _put_label(image, label, int(cx), int(corners[:, 1].min()) - 12, COLOR_MRK)


def draw_measurement(image, x1, y1, x2, y2, measurements, label="Объект"):
    cv2.rectangle(image, (x1, y1), (x2, y2), COLOR_OBJ, 2)
    lines = [f"{label}", f"W: {measurements['width_m']*100:.1f} cm", f"H: {measurements['height_m']*100:.1f} cm"]
    if "depth_m" in measurements: lines.append(f"Z: {measurements['depth_m']:.2f} m")
    tx = x1; ty = y1 - 10 - (len(lines) - 1) * 22
    for line in lines:
        _put_label(image, line, tx, ty, COLOR_OBJ)
        ty += 22
    _draw_dim_arrow(image, x1, y2 + 15, x2, y2 + 15, f"{measurements['width_m']*100:.1f} cm", COLOR_OBJ)
    _draw_dim_arrow(image, x2 + 15, y1, x2 + 15, y2, f"{measurements['height_m']*100:.1f} cm", COLOR_OBJ, vertical=True)


def _put_label(image, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, FONT, 0.6, 1)
    cv2.rectangle(image, (x - 2, y - th - 4), (x + tw + 2, y + 4), COLOR_BG, -1)
    cv2.putText(image, text, (x, y), FONT, 0.6, color, 2, cv2.LINE_AA)


def _draw_dim_arrow(image, x1, y1, x2, y2, label, color, vertical=False):
    cv2.arrowedLine(image, (x1, y1), (x2, y2), color, 1, tipLength=0.05)
    cv2.arrowedLine(image, (x2, y2), (x1, y1), color, 1, tipLength=0.05)
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    _put_label(image, label, mx, my, color)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Публичный API
# ─────────────────────────────────────────────────────────────────────────────

def measure_object_auto(
    image_bgr: np.ndarray,
    marker_size_m: float,
    depth_map: np.ndarray,
    aruco_dict: Optional[str] = None,
    object_label: str = "Объект",
    same_plane: bool = True,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    expected_marker_id: Optional[int] = None,
) -> Tuple[Optional[Dict[str, float]], np.ndarray, Optional[np.ndarray]]:
    result_img = image_bgr.copy()
    
    corners, marker_id, dict_name = detect_aruco(image_bgr, aruco_dict, expected_marker_id=expected_marker_id)
    if corners is None:
        logger.error("Маркёр не найден")
        return None, result_img, None
    
    marker_bbox_cv = cv2.boundingRect(corners.astype(np.float32))
    marker_bbox = tuple(marker_bbox_cv)
    draw_marker(result_img, corners, marker_id, marker_size_m)
    
    scale = ScaleEstimator(corners, marker_size_m, depth_map, same_plane=same_plane)
    
    # Здесь срабатывает логика игнорирования маркёра
    seg_result = segment_object_from_depth(
        depth_map, 
        image_bgr, 
        marker_bbox=marker_bbox,
        manual_roi=manual_roi,
    )
    
    if seg_result is None:
        logger.error("Не удалось сегментировать объект")
        return None, result_img, None
    
    bbox, object_mask = seg_result
    measurements = measure_bbox_rotated(result_img, bbox, scale)
    
    draw_measurement(result_img, bbox[0], bbox[1], bbox[2], bbox[3], measurements, object_label)
    
    mask_overlay = result_img.copy()
    mask_overlay[object_mask] = (mask_overlay[object_mask] * 0.7 + np.array([0, 255, 0]) * 0.3).astype(np.uint8)
    cv2.addWeighted(mask_overlay, 0.5, result_img, 0.5, 0, result_img)
    
    logger.info(f"Результат [{object_label}]: W={measurements['width_m']*100:.1f} cm, H={measurements['height_m']*100:.1f} cm")
    return measurements, result_img, object_mask


def measure_from_wrapper(
    image_bgr: np.ndarray,
    wrapper,
    marker_size_m: float,
    multi_scale: bool = False,
    object_label: str = "Объект",
    same_plane: bool = True,
    enhance_visualization: bool = True,
    gamma: float = 0.75,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
    expected_marker_id: Optional[int] = None,
) -> Tuple[Optional[Dict[str, float]], np.ndarray, np.ndarray]:
    logger.info("Запуск DA-V2 (metric depth)...")
    depth_map = wrapper.estimate(image_bgr, multi_scale=multi_scale)
    
    if enhance_visualization:
        depth_vis = enhance_depth_visualization(
            depth_map, bbox=None, gamma=gamma, colormap=cv2.COLORMAP_VIRIDIS
        )
    else:
        depth_vis = wrapper.estimate_visual(image_bgr, normalize="metric_range", multi_scale=multi_scale)
    
    measurements, annotated, object_mask = measure_object_auto(
        image_bgr, marker_size_m=marker_size_m, depth_map=depth_map,
        object_label=object_label, same_plane=same_plane,
        manual_roi=manual_roi,
        expected_marker_id=expected_marker_id,
    )
    return measurements, annotated, depth_vis


# ─────────────────────────────────────────────────────────────────────────────
# 6. CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description="ArUco object measurement (Auto Mode)")
    p.add_argument("--image", required=True)
    p.add_argument("--marker-size", type=float, default=0.055)
    p.add_argument("--output", default="measurement_result.jpg")
    p.add_argument("--label", default="Object")
    p.add_argument("--gamma", type=float, default=0.75)
    return p.parse_args()

if __name__ == "__main__":
    print("Тест")