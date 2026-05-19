from aruco_measure import measure_object
from optimized_wrapper import DepthAnythingV2OpenVINO
import cv2
import numpy as np
from celery_app import celery_app
from pathlib import Path
import sys

# Добавляем корень проекта в путь, чтобы импортировать ваши скрипты
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# Инициализация модели (кэшируется между задачами)
_model = DepthAnythingV2OpenVINO(
    ir_path="ir_model/ir_metric_hypersim_vitb",
    model_size="vitb",
    metric=True,
    scene_type="indoor",
)


@celery_app.task(bind=True, max_retries=1)
def process_measurement_task(self, image_paths: list[str], marker_size_mm: float):
    """
    Принимает пути к 3 фото (front, side, top) и размер маркера.
    Возвращает JSON с габаритами и статусами.
    """
    try:
        results = {}
        views = ["front", "side", "top"]

        for view, img_path in zip(views, image_paths):
            img = cv2.imread(img_path)
            if img is None:
                raise ValueError(f"Не удалось прочитать: {img_path}")

            # Оценка глубины
            depth_map = _model.estimate(img, multi_scale=True)

            # Измерение с ArUco (bbox=None → интерактивный режим пока отключим,
            # позже заменим на автосегментацию или передадим bbox с фронта)
            measurements, annotated = measure_object(
                img,
                marker_size_m=marker_size_mm / 1000.0,
                depth_map=depth_map,
                interactive=False,  # Для продакшена ставим False
                object_label=view.capitalize(),
            )

            results[view] = {
                "status": "ok" if measurements else "error",
                "width_mm": measurements.get("width_m", 0) * 100 if measurements else None,
                "height_mm": measurements.get("height_m", 0) * 100 if measurements else None,
                "depth_m": measurements.get("depth_m"),
            }

        return {"status": "success", "results": results}

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
