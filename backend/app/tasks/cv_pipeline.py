"""
Celery-задачи для конвейера компьютерного зрения.
Реализует статусную модель обработки измерений.
Включает поддержку ручного ROI.
"""
from __future__ import annotations
import logging
import contextlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import psycopg2
from psycopg2.extensions import connection as PgConnection

from app.core.celery_app import celery_app
from app.core.config import settings
from app.cv.aruco_measure import measure_from_wrapper
from app.cv.optimized_wrapper import DepthAnythingV2OpenVINO
from app.db.enums import MeasurementStatus
from app.services.verifier import DimensionVerifier

logger = logging.getLogger(__name__)

REQUIRED_VIEWS: Tuple[str, str, str] = ("front", "side", "top")
DIMENSION_MAPPING: Dict[str, Tuple[str, str]] = {
    "length": ("front", "height_mm"),
    "width": ("side", "height_mm"),
    "height": ("top", "height_mm"),
}
MM_PER_METER: float = 1000.0

_depth_model_cache: Dict[str, DepthAnythingV2OpenVINO] = {}

def get_cached_depth_model() -> DepthAnythingV2OpenVINO:
    cache_key = "metric"
    if cache_key not in _depth_model_cache:
        logger.info("Загрузка модели Depth Anything V2...")
        _depth_model_cache[cache_key] = DepthAnythingV2OpenVINO(
            ir_path=settings.cv_model_ir_path,
            model_size=settings.cv_model_size,
            metric=True,
            scene_type=settings.cv_scene_type,
            device="CPU",
        )
    return _depth_model_cache[cache_key]

@contextlib.contextmanager
def get_database_connection() -> PgConnection:
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = psycopg2.connect(db_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def execute_db_update(query: str, params: tuple, operation_name: str, measurement_id: Optional[int] = None) -> bool:
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return True
    except Exception as error:
        logger.error(f"DB Error {operation_name}: {error}")
        return False

def create_measurement_record(user_id: int, product_id: Optional[int], initial_dimensions: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> int:
    query = """
        INSERT INTO measurements (user_id, product_id, length_mm, width_mm, height_mm, status)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """
    params = (user_id, product_id, *initial_dimensions, MeasurementStatus.PENDING.value)
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()[0]

def update_measurement_status(measurement_id: int, status: MeasurementStatus) -> bool:
    return execute_db_update("UPDATE measurements SET status = %s WHERE id = %s", (status.value, measurement_id), "Status Update")

def finalize_measurement(measurement_id: int, dimensions: Dict[str, float], status: MeasurementStatus, verification_metrics: Dict[str, Optional[float]]) -> bool:
    query = """
        UPDATE measurements 
        SET length_mm = %s, width_mm = %s, height_mm = %s, status = %s, delta_pct = %s, verified_ok = %s, measured_at = NOW()
        WHERE id = %s
    """
    params = (dimensions["length_mm"], dimensions["width_mm"], dimensions["height_mm"], status.value, verification_metrics.get("delta_pct"), verification_metrics.get("verified_ok"), measurement_id)
    return execute_db_update(query, params, "Finalize")

def process_single_view(
    image_path: str,
    model: DepthAnythingV2OpenVINO,
    marker_size_meters: float,
    view_label: str,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, float]:
    logger.info(f"Processing {view_label}, image_path={image_path}, roi={manual_roi}")
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise ValueError(f"Не удалось прочитать изображение: {image_path}")
    
    # Вызываем обертку с передачей ROI
    measurements, annotated, depth_vis = measure_from_wrapper(
        image_bgr=image_bgr,
        wrapper=model,
        marker_size_m=marker_size_meters,
        multi_scale=False,
        object_label=view_label.capitalize(),
        same_plane=True,
        manual_roi=manual_roi,  # <-- Передача ROI
    )

    if measurements is None:
        # Логируем больше деталей для отладки
        logger.error(f"Измерение вернуло None для ракурса {view_label}. Проверьте сегментацию.")
        raise ValueError(f"Не удалось измерить объект на ракурсе {view_label}")

    return {
        "width_mm": measurements["width_m"] * MM_PER_METER,
        "height_mm": measurements["height_m"] * MM_PER_METER,
        "depth_m": measurements.get("depth_m", 0.0),
        "confidence": measurements.get("confidence", 1.0),
    }

@celery_app.task(bind=True, max_retries=1)
def process_measurement_task(
    self: Any,
    image_paths: List[str],
    marker_size_mm: float,
    user_id: int,
    product_id: Optional[int] = None,
    manual_roi: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, Any]:
    measurement_id: Optional[int] = None
    try:
        if len(image_paths) != len(REQUIRED_VIEWS):
            raise ValueError(f"Требуется ровно {len(REQUIRED_VIEWS)} изображения")

        measurement_id = create_measurement_record(user_id=user_id, product_id=product_id)
        update_measurement_status(measurement_id, MeasurementStatus.PROCESSING)

        model = get_cached_depth_model()
        views = ["front", "side", "top"]
        view_results: Dict[str, Dict[str, float]] = {}
        confidences: List[float] = []
        marker_size_meters = marker_size_mm / MM_PER_METER

        for view_name, img_path in zip(views, image_paths):
            view_results[view_name] = process_single_view(
                image_path=img_path,
                model=model,
                marker_size_meters=marker_size_meters,
                view_label=view_name,
                manual_roi=manual_roi, # <-- Передача ROI в каждый ракурс
            )
            confidences.append(view_results[view_name]["confidence"])

        dimensions = {f"{dim_name}_mm": view_results[view_name][result_key] for dim_name, (view_name, result_key) in DIMENSION_MAPPING.items()}
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        final_status = MeasurementStatus.COMPLETED
        verify_res = DimensionVerifier(10.0).verify(
            measured={k.replace("_mm", "") + "_mm": v for k, v in dimensions.items()},
            reference=None, 
            confidence=avg_confidence
        )
        if not verify_res.ok:
            final_status = MeasurementStatus.NEEDS_REVIEW

        finalize_measurement(
            measurement_id=measurement_id,
            dimensions=dimensions,
            status=final_status,
            verification_metrics={"delta_pct": verify_res.delta_pct, "verified_ok": verify_res.ok},
        )
        
        # Cleanup
        for path in image_paths:
            if Path(path).exists(): Path(path).unlink()

        return {"status": "success", "measurement_id": measurement_id, "final_status": final_status.value, "confidence": avg_confidence, "dimensions_mm": dimensions}

    except Exception as error:
        logger.error(f"Critical error: {error}", exc_info=True)
        if measurement_id is not None:
            update_measurement_status(measurement_id, MeasurementStatus.FAILED)
        raise self.retry(exc=error, countdown=5)