import logging
import cv2
import numpy as np
from pathlib import Path
import psycopg2
from app.core.celery_app import celery_app
from app.core.config import settings
from app.cv.optimized_wrapper import DepthAnythingV2OpenVINO
from app.cv.aruco_measure import measure_from_wrapper

logger = logging.getLogger(__name__)

_model_cache = {}

def get_depth_model():
    if "metric" not in _model_cache:
        logger.info("Loading Depth Anything V2 Metric model...")
        _model_cache["metric"] = DepthAnythingV2OpenVINO(
            ir_path=settings.cv_model_ir_path,
            model_size=settings.cv_model_size,
            metric=True,
            scene_type=settings.cv_scene_type,
            device="CPU"
        )
    return _model_cache["metric"]

def save_to_db_sync(user_id: int, product_id: int, length_mm: float, width_mm: float, height_mm: float):
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO measurements 
            (user_id, product_id, length_mm, width_mm, height_mm, verified_ok, delta_pct, override_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, product_id, length_mm, width_mm, height_mm, None, None, None))
        measurement_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"Measurement saved with ID: {measurement_id}")
        return measurement_id
    except Exception as e:
        logger.error(f"DB Error: {e}")
        if conn: conn.rollback()
        raise e
    finally:
        if conn: conn.close()

@celery_app.task(bind=True, max_retries=1)
def process_measurement_task(self, image_paths: list[str], marker_size_mm: float, user_id: int, product_id: int = None):
    try:
        if len(image_paths) != 3:
            raise ValueError("Требуется ровно 3 изображения: front, side, top")

        model = get_depth_model()
        views = ["front", "side", "top"]
        results = {}

        for view_name, img_path in zip(views, image_paths):
            logger.info(f"Processing view: {view_name}")
            img = cv2.imread(img_path)
            if img is None:
                raise ValueError(f"Не удалось прочитать изображение: {img_path}")

            # АВТОМАТИЧЕСКИЙ ПАЙПЛАЙН: глубина + ArUco + авто-сегментация + измерение
            measurements, annotated, depth_vis = measure_from_wrapper(
                image_bgr=img,
                wrapper=model,
                marker_size_m=marker_size_mm / 1000.0,
                multi_scale=False,
                object_label=view_name.capitalize(),
                same_plane=True,
                enhance_visualization=True,
                gamma=0.75
            )

            if measurements is None:
                raise ValueError(f"Не удалось измерить объект на ракурсе {view_name}.")

            results[view_name] = {
                "width_mm": measurements['width_m'] * 1000,
                "height_mm": measurements['height_m'] * 1000,
                "depth_m": measurements.get('depth_m', 0)
            }
            logger.info(f"[{view_name}] W={results[view_name]['width_mm']:.1f}mm, H={results[view_name]['height_mm']:.1f}mm")

        # Агрегация (фронт→длина, бок→ширина, верх→высота)
        final_length = results["front"]["height_mm"]
        final_width = results["side"]["height_mm"]
        final_height = results["top"]["height_mm"]

        measurement_id = save_to_db_sync(
            user_id=user_id, product_id=product_id,
            length_mm=final_length, width_mm=final_width, height_mm=final_height
        )

        return {"status": "success", "measurement_id": measurement_id}

    except Exception as exc:
        logger.error(f"Error processing measurement: {exc}")
        raise self.retry(exc=exc, countdown=5)