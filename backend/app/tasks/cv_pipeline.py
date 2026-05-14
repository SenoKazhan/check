"""
Celery-задачи для конвейера компьютерного зрения.
Реализует статусную модель: PENDING → PROCESSING → COMPLETED/FAILED
"""
import logging
import cv2
import numpy as np
from pathlib import Path
import psycopg2  # Синхронный драйвер для использования в Celery-воркере
from app.core.celery_app import celery_app
from app.core.config import settings
from app.cv.optimized_wrapper import DepthAnythingV2OpenVINO
from app.cv.aruco_measure import measure_from_wrapper
from app.db.models.measurement import MeasurementStatus

logger = logging.getLogger(__name__)

_model_cache = {}

def get_depth_model():
    """Ленивая загрузка модели с кэшированием."""
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


def _update_status_sync(measurement_id: int, status: MeasurementStatus) -> bool:
    """
    Синхронный хелпер для обновления статуса из Celery-воркера.
    
    Почему sync? Celery-воркеры работают в отдельных процессах,
    и использование asyncpg требует event loop, который в Celery
    по умолчанию не инициализирован.
    """
    # Конвертируем asyncpg URL в psycopg2 формат
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(
            "UPDATE measurements SET status = %s WHERE id = %s",
            (status.value, measurement_id)
        )
        conn.commit()
        logger.info(f"✓ Measurement #{measurement_id}: status → {status.value}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to update status #{measurement_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def _create_measurement_record(
    user_id: int, 
    product_id: int | None,
    initial_dims: tuple[float, float, float] = (0.0, 0.0, 0.0)
) -> int:
    """Создаёт запись измерения со статусом PENDING."""
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO measurements 
            (user_id, product_id, length_mm, width_mm, height_mm, 
             status, verified_ok, delta_pct, override_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id, 
            product_id, 
            *initial_dims,  # Распаковка (l, w, h)
            MeasurementStatus.PENDING.value,
            None, None, None
        ))
        measurement_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"✓ Created measurement record #{measurement_id}")
        return measurement_id
    except Exception as e:
        logger.error(f"✗ Failed to create measurement record: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _update_measurement_results(
    measurement_id: int,
    length_mm: float,
    width_mm: float, 
    height_mm: float,
    status: MeasurementStatus = MeasurementStatus.COMPLETED
) -> bool:
    """Обновляет результаты измерения и статус."""
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = None
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("""
            UPDATE measurements 
            SET length_mm = %s, width_mm = %s, height_mm = %s, 
                status = %s, measured_at = NOW()
            WHERE id = %s
        """, (length_mm, width_mm, height_mm, status.value, measurement_id))
        conn.commit()
        logger.info(f"✓ Updated measurement #{measurement_id}: {status.value}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to update measurement #{measurement_id}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


@celery_app.task(bind=True, max_retries=1)
def process_measurement_task(
    self, 
    image_paths: list[str], 
    marker_size_mm: float, 
    user_id: int, 
    product_id: int = None,
    confidence_threshold: float = 0.4
):
    """
    Основная задача обработки измерений.
    
    Статусная машина:
    1. CREATE → PENDING (перед началом обработки)
    2. UPDATE → PROCESSING (начало CV-пайплайна)
    3. UPDATE → COMPLETED (успех) или FAILED (ошибка) или NEEDS_REVIEW (низкий confidence)
    """
    measurement_id = None
    
    try:
        # === Валидация входных данных ===
        if len(image_paths) != 3:
            raise ValueError("Требуется ровно 3 изображения: front, side, top")

        # === Шаг 1: Создаём запись со статусом PENDING ===
        measurement_id = _create_measurement_record(
            user_id=user_id,
            product_id=product_id,
            initial_dims=(0.0, 0.0, 0.0)  # Плейсхолдеры до расчёта
        )

        # === Шаг 2: Обновляем статус на PROCESSING ===
        _update_status_sync(measurement_id, MeasurementStatus.PROCESSING)

        # === Шаг 3: Запускаем CV-пайплайн ===
        model = get_depth_model()
        views = ["front", "side", "top"]
        results = {}
        confidences = []  # Для оценки надёжности результата

        for view_name, img_path in zip(views, image_paths):
            logger.info(f"Processing view: {view_name}")
            
            img = cv2.imread(img_path)
            if img is None:
                raise ValueError(f"Не удалось прочитать изображение: {img_path}")

            # Автоматический пайплайн: глубина + ArUco + сегментация + измерение
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

            # Сохраняем результаты и confidence
            results[view_name] = {
                "width_mm": measurements['width_m'] * 1000,
                "height_mm": measurements['height_m'] * 1000,
                "depth_m": measurements.get('depth_m', 0)
            }
            confidences.append(measurements.get('confidence', 0.0))
            
            logger.info(
                f"[{view_name}] W={results[view_name]['width_mm']:.1f}mm, "
                f"H={results[view_name]['height_mm']:.1f}mm, "
                f"conf={measurements.get('confidence', 0):.2f}"
            )

        # === Шаг 4: Агрегация результатов ===
        final_length = results["front"]["height_mm"]
        final_width = results["side"]["height_mm"]
        final_height = results["top"]["height_mm"]
        
        # Оценка надёжности: средняя уверенность по всем ракурсам
        avg_confidence = np.mean(confidences) if confidences else 0.0

        # === Шаг 5: Определение финального статуса ===
        if avg_confidence < confidence_threshold:
            final_status = MeasurementStatus.NEEDS_REVIEW
            logger.warning(
                f"Low confidence ({avg_confidence:.2f} < {confidence_threshold}): "
                f"measurement #{measurement_id} marked for review"
            )
        else:
            final_status = MeasurementStatus.COMPLETED

        # === Шаг 6: Сохранение результатов ===
        _update_measurement_results(
            measurement_id=measurement_id,
            length_mm=final_length,
            width_mm=final_width,
            height_mm=final_height,
            status=final_status
        )

        return {
            "status": "success",
            "measurement_id": measurement_id,
            "final_status": final_status.value,
            "confidence": avg_confidence,
            "dimensions_mm": {
                "length": final_length,
                "width": final_width,
                "height": final_height
            }
        }

    except Exception as exc:
        logger.error(f"Error processing measurement: {exc}", exc_info=True)
        
        # Обновляем статус на FAILED, если запись была создана
        if measurement_id is not None:
            _update_status_sync(measurement_id, MeasurementStatus.FAILED)
        
        # Повторная попытка через 5 секунд (макс. 1 повтор)
        raise self.retry(exc=exc, countdown=5)
    
# app/tasks/cv_pipeline.py
from app.db.sync_session import get_sync_session
from app.db.models import Measurement

def save_measurement_sync(user_id: int, product_id: int | None, 
                         length_mm: float, width_mm: float, height_mm: float) -> int:
    with get_sync_session() as session:
        measurement = Measurement(
            user_id=user_id,
            product_id=product_id,
            length_mm=length_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            status="completed"  # ← если добавили поле status
        )
        session.add(measurement)
        session.commit()
        return measurement.id