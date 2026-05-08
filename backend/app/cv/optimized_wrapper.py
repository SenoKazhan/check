import logging
import cv2
import numpy as np
from pathlib import Path
import openvino as ov
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Предустановленные внутренние параметры камеры для метрической глубины.
# Используются, если пользователь не передаёт fx/fy/cx/cy явно.
# ─────────────────────────────────────────────────────────────────────────────
PRESET_INTRINSICS: Dict[str, Dict[str, float]] = {
    # Типовая webcam / телефон (эквивалент ~70° hFOV на 1280×720)
    "generic": {"fx": 886.81, "fy": 886.81, "cx": 640.0, "cy": 360.0},
    # KITTI (на котором обучена метрическая модель indoor/outdoor)
    "kitti":   {"fx": 721.54, "fy": 721.54, "cx": 609.56, "cy": 172.85},
    # NYU Depth V2 (indoor)
    "nyu":     {"fx": 519.0,  "fy": 519.0,  "cx": 325.58, "cy": 253.74},
}

# Диапазоны валидной глубины (в метрах) по типу сцены
DEPTH_RANGE: Dict[str, Tuple[float, float]] = {
    "indoor":  (0.1, 10.0),
    "outdoor": (0.5, 80.0),
    "generic": (0.1, 80.0),
}


class DepthAnythingV2OpenVINO:
    """
    OpenVINO-обёртка для Depth Anything V2.

    Поддерживает два режима:
      • relative  — относительная глубина (исходная модель vits/vitb/vitl)
      • metric    — метрическая глубина в метрах (модели *_metric_*)

    Параметры
    ---------
    model_size  : 'small' | 'base' | 'large'
    device      : 'CPU' | 'GPU'
    ir_path     : путь к папке с .xml/.bin (если None — авто-выбор по режиму)
    metric      : True → метрический режим
    scene_type  : 'indoor' | 'outdoor' | 'generic'  (только для metric)
    intrinsics  : имя пресета ('generic'/'kitti'/'nyu') или dict с fx,fy,cx,cy
    max_depth   : верхний порог глубины в метрах (только для metric, None = авто)
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "CPU",
        ir_path: Optional[str] = None,
        metric: bool = False,
        scene_type: str = "generic",
        intrinsics: Optional[Any] = "generic",
        max_depth: Optional[float] = None,
        **kwargs,
    ):
        self.model_size = model_size.lower()
        self.device = device.upper()
        self.metric = metric
        self.scene_type = scene_type

        # ── Внутренние параметры камеры ──────────────────────────────────────
        if isinstance(intrinsics, str):
            self.intrinsics = PRESET_INTRINSICS.get(
                intrinsics, PRESET_INTRINSICS["generic"])
        elif isinstance(intrinsics, dict):
            self.intrinsics = intrinsics
        else:
            self.intrinsics = PRESET_INTRINSICS["generic"]

        # ── Диапазон глубины ─────────────────────────────────────────────────
        d_min, d_max = DEPTH_RANGE.get(scene_type, DEPTH_RANGE["generic"])
        self.depth_min = d_min
        self.depth_max = max_depth if max_depth is not None else d_max

        # ── Путь к IR-модели ─────────────────────────────────────────────────
        if ir_path is not None:
            self.ir_path = Path(ir_path)
        else:
            # Если путь не передан явно, ищем относительно текущего файла (optimized_wrapper.py)
            # Это гарантирует, что воркер найдёт модель, даже если запущен из корня backend/
            current_dir = Path(__file__).resolve().parent
            if metric:
                self.ir_path = current_dir / \
                    f"ir_model/ir_{self.model_size}_metric"
            else:
                self.ir_path = current_dir / f"ir_model/ir_{self.model_size}"

        # Пробуем оба варианта имени файла (с суффиксом _metric и без)
        candidates = [
            self.ir_path /
            f"depth_anything_v2_metric_hypersim_{self.model_size}.xml",
            self.ir_path /
            f"depth_anything_v2_metric_vkitti_{self.model_size}.xml",
            self.ir_path / f"depth_anything_v2_{self.model_size}_metric.xml",
            self.ir_path / f"depth_anything_v2_{self.model_size}.xml",
        ]

        model_xml = next((p for p in candidates if p.exists()), None)

        if model_xml is None:
            # Для отладки выведем абсолютные пути, которые искал воркер
            raise FileNotFoundError(
                f"OpenVINO IR модель не найдена. Искал:\n"
                + "\n".join(f"  • {p.absolute()}" for p in candidates)
            )

        # ── Загрузка модели ──────────────────────────────────────────────────
        try:
            core = ov.Core()
            self.compiled_model = core.compile_model(
                str(model_xml), self.device)
            self.input_layer = self.compiled_model.input(0)
            self.output_layer = self.compiled_model.output(0)
            mode_label = "METRIC" if metric else "RELATIVE"
            logger.info(
                f"[OpenVINO] ✅ {mode_label} | {self.model_size.upper()} | "
                f"Device: {self.device} | Scene: {scene_type}"
            )
        except Exception as e:
            logger.error(f"[OpenVINO] ❌ Ошибка загрузки модели: {e}")
            raise

        # ── Настройки визуализации ───────────────────────────────────────────
        self.colormap_map = {
            "inferno": cv2.COLORMAP_INFERNO,
            "viridis": cv2.COLORMAP_VIRIDIS,
            "plasma":  cv2.COLORMAP_PLASMA,
            "jet":     cv2.COLORMAP_JET,
            "magma":   cv2.COLORMAP_MAGMA,
            "hot":     cv2.COLORMAP_HOT,
        }
        self.colormap = kwargs.get("colormap", "inferno")
        self.invert = kwargs.get("invert", True)

    # ─────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ─────────────────────────────────────────────────────────────────────────

    def _preprocess(self, image_bgr: np.ndarray) -> np.ndarray:
        """Нормализация и приведение к (1, 3, 518, 518)."""
        img_resized = cv2.resize(
            image_bgr, (518, 518), interpolation=cv2.INTER_LINEAR)
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_chw = np.transpose(img_norm, (2, 0, 1))
        return np.expand_dims(img_chw, axis=0)

    def _run_inference(self, image_bgr: np.ndarray) -> np.ndarray:
        """Один прогон через сеть, возвращает сырой 2D-массив."""
        inp = self._preprocess(image_bgr)
        res = self.compiled_model({self.input_layer.any_name: inp})
        depth = np.squeeze(res[self.output_layer.any_name])
        if depth.ndim != 2:
            raise ValueError(
                f"Неверная форма выхода модели: {depth.shape}. Ожидалось 2D.")
        return depth

    def _postprocess_metric(self, depth_raw: np.ndarray) -> np.ndarray:
        """
        Постобработка метрической глубины:
          1. Клиппинг к валидному диапазону сцены
          2. Масштабирование с учётом focal length (если нужна коррекция на реальные интринсики)

        Метрическая модель DA-V2 обучена на KITTI (fx≈721) и Hypersim.
        Если ваша камера сильно отличается, применяем грубую коррекцию через отношение focal.
        """
        depth = np.clip(depth_raw.astype(np.float32),
                        self.depth_min, self.depth_max)

        # Коррекция focal length (необязательна, но улучшает абсолютную точность)
        kitti_fx = PRESET_INTRINSICS["kitti"]["fx"]
        your_fx = self.intrinsics.get("fx", kitti_fx)
        if abs(your_fx - kitti_fx) > 20:           # только если разница ощутима
            scale = kitti_fx / your_fx
            depth = np.clip(depth * scale, self.depth_min, self.depth_max)

        return depth

    # ─────────────────────────────────────────────────────────────────────────
    # Публичный API
    # ─────────────────────────────────────────────────────────────────────────

    def estimate(
        self,
        image_bgr: np.ndarray,
        multi_scale: bool = False,
        **kwargs,
    ) -> np.ndarray:
        """
        Инференс карты глубины.

        Returns
        -------
        np.ndarray (H, W), float32
          • Relative mode: безразмерные значения, большие = ближе к камере
          • Metric mode:   значения в метрах, большие = дальше от камеры
        """
        h, w = image_bgr.shape[:2]

        if not multi_scale:
            depth_raw = self._run_inference(image_bgr)
            depth = cv2.resize(
                depth_raw, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
        else:
            scales = [0.75, 1.0, 1.25]
            depth_sum = np.zeros((h, w), dtype=np.float32)
            for scale in scales:
                nw, nh = int(w * scale), int(h * scale)
                resized = cv2.resize(image_bgr, (nw, nh),
                                     interpolation=cv2.INTER_LINEAR)
                d_raw = self._run_inference(resized)
                depth_sum += cv2.resize(d_raw, (w, h),
                                        interpolation=cv2.INTER_LINEAR)
            depth = (depth_sum / len(scales)).astype(np.float32)

        if self.metric:
            depth = self._postprocess_metric(depth)

        return depth

    def estimate_metric(
        self,
        image_bgr: np.ndarray,
        multi_scale: bool = False,
        **kwargs,
    ) -> np.ndarray:
        """
        Явный вызов метрического режима (удобно, если объект создан без metric=True).

        Returns
        -------
        np.ndarray (H, W), float32 — глубина в метрах
        """
        was_metric = self.metric
        self.metric = True
        try:
            depth_m = self.estimate(
                image_bgr, multi_scale=multi_scale, **kwargs)
        finally:
            self.metric = was_metric
        return depth_m

    def estimate_visual(
        self,
        image_bgr: np.ndarray,
        normalize: str = "percentile",
        **kwargs,
    ) -> np.ndarray:
        """
        Визуализация карты глубины с colormap.

        Parameters
        ----------
        normalize : 'percentile' | 'minmax' | 'histogram' | 'metric_range'
            'metric_range' нормирует по self.depth_min / self.depth_max
            (удобно для метрического режима, чтобы цвет = реальная дистанция).

        Returns
        -------
        np.ndarray (H, W, 3), uint8, BGR
        """
        depth = self.estimate(image_bgr, **kwargs)

        if normalize == "metric_range" or (self.metric and normalize == "percentile"):
            # Нормировка по реальному диапазону → цвет сохраняет смысл метров
            depth_norm = np.clip(
                (depth - self.depth_min) /
                (self.depth_max - self.depth_min + 1e-8),
                0.0, 1.0,
            )
        elif normalize == "percentile":
            p_min, p_max = np.percentile(depth, (2, 98))
            depth_norm = np.clip(
                (depth - p_min) / (p_max - p_min + 1e-8), 0.0, 1.0)
        elif normalize == "histogram":
            depth_uint8 = (
                np.clip(depth / (self.depth_max + 1e-8), 0, 1) * 255
                if self.metric
                else depth * 255
            ).astype(np.uint8)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            depth_norm = clahe.apply(depth_uint8).astype(np.float32) / 255.0
        else:  # minmax
            depth_norm = (depth - depth.min()) / \
                (depth.max() - depth.min() + 1e-8)

        # В метрическом режиме дальнее = большое → НЕ инвертируем (ближнее тёплое)
        # В относительном режиме модель возвращает "ближнее = большое" → инвертируем
        should_invert = self.invert if not self.metric else False
        if should_invert:
            depth_norm = 1.0 - depth_norm

        depth_u8 = (depth_norm * 255).astype(np.uint8)
        cmap = self.colormap_map.get(self.colormap, cv2.COLORMAP_INFERNO)
        return cv2.applyColorMap(depth_u8, cmap)

    def get_depth_at_point(
        self,
        image_bgr: np.ndarray,
        x: int,
        y: int,
        patch: int = 5,
        **kwargs,
    ) -> Optional[float]:
        """
        Возвращает глубину в конкретной точке изображения (в метрах для metric=True).

        Parameters
        ----------
        x, y  : координаты пикселя
        patch : размер окна усреднения (нечётное число)

        Returns
        -------
        float или None, если точка вне изображения
        """
        h, w = image_bgr.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return None

        depth = self.estimate(image_bgr, **kwargs)
        half = patch // 2
        y0, y1 = max(0, y - half), min(h, y + half + 1)
        x0, x1 = max(0, x - half), min(w, x + half + 1)
        return float(np.median(depth[y0:y1, x0:x1]))

    def estimate_with_overlay(
        self,
        image_bgr: np.ndarray,
        alpha: float = 0.6,
        normalize: str = "percentile",
        **kwargs,
    ) -> np.ndarray:
        """
        Возвращает исходное изображение с полупрозрачным наложением карты глубины.

        Parameters
        ----------
        alpha : вес карты глубины (0 = только оригинал, 1 = только глубина)
        """
        depth_vis = self.estimate_visual(
            image_bgr, normalize=normalize, **kwargs)
        return cv2.addWeighted(image_bgr, 1 - alpha, depth_vis, alpha, 0)

    def estimate_stats(self, image_bgr: np.ndarray, **kwargs) -> Dict[str, float]:
        """
        Статистика карты глубины — удобно для отладки и логирования в диплом.

        Returns
        -------
        dict с ключами: min, max, mean, median, std, p5, p95
        Для metric=True значения в метрах.
        """
        depth = self.estimate(image_bgr, **kwargs)
        return {
            "min":    float(depth.min()),
            "max":    float(depth.max()),
            "mean":   float(depth.mean()),
            "median": float(np.median(depth)),
            "std":    float(depth.std()),
            "p5":     float(np.percentile(depth, 5)),
            "p95":    float(np.percentile(depth, 95)),
        }


# Псевдоним для обратной совместимости с test.py
DepthAnythingV2WrapperImproved = DepthAnythingV2OpenVINO
