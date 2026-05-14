"""
Celery-задачи для конвейера компьютерного зрения.
Реализует статусную модель: PENDING → PROCESSING → COMPLETED/FAILED/NEEDS_REVIEW

Все DB-операции выполняются синхронно через psycopg2, так как Celery-воркеры
не имеют event loop по умолчанию.
"""
import logging
import cv2
import numpy as np
from pathlib import Path
import psycopg2
from typing import Optional

from app.core.celery_app import celery_app
from app.core.config import settings
from app.cv.optimized_wrapper import DepthAnythingV2OpenVINO
from app.cv.aruco_measure import measure_from_wrapper
from app.db.models.measurement import MeasurementStatus

logger = logging.getLogger(__name__)

# Глобальный кэш модели для повторного использования в воркере
_model_cache: dict[str, DepthAnythingV2OpenVINO] = {}

def get_depth_model() -> DepthAnythingV2OpenVINO:
    """Ленивая загрузка модели с кэшированием в памяти воркера."""
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


def _get_sync_db_connection():
    """Создаёт синхронное подключение к БД для использования в Celery."""
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return psycopg2.connect(db_url)


def _update_status_sync(measurement_id: int, status: MeasurementStatus) -> bool:
    """Обновляет статус измерения в БД (синхронно)."""
    conn = None
    try:
        conn = _get_sync_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE measurements SET status = %s WHERE id = %s",
            (status.value, measurement_id)
        )
        conn.commit()
        logger.info(f"✓ Measurement #{measurement_id}: status → {status.value}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to update status #{measurement_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def _create_measurement_record(
    user_id: int, 
    product_id: Optional[int],
    initial_dims: tuple[float, float, float] = (0.0, 0.0, 0.0)
) -> int:
    """Создаёт запись измерения со статусом PENDING и возвращает её ID."""
    conn = None
    try:
        conn = _get_sync_db_connection()
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
            *initial_dims,
            MeasurementStatus.PENDING.value,
            None, None, None
        ))
        measurement_id = cur.fetchone()[0]
        conn.commit()
        logger.info(f"✓ Created measurement record #{measurement_id}")
        return measurement_id
    except Exception as e:
        logger.error(f"✗ Failed to create measurement record: {e}", exc_info=True)
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
    status: MeasurementStatus = MeasurementStatus.COMPLETED,
    delta_pct: Optional[float] = None,
    verified_ok: Optional[bool] = None
) -> bool:
    """Обновляет результаты измерения и финальный статус."""
    conn = None
    try:
        conn = _get_sync_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE measurements 
            SET length_mm = %s, width_mm = %s, height_mm = %s, 
                status = %s, delta_pct = %s, verified_ok = %s, measured_at = NOW()
            WHERE id = %s
        """, (length_mm, width_mm, height_mm, status.value, delta_pct, verified_ok, measurement_id))
        conn.commit()
        logger.info(f"✓ Updated measurement #{measurement_id}: {status.value}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to update measurement #{measurement_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def _cleanup_temp_files(file_paths: list[str]) -> None:
    """Удаляет временные файлы после обработки."""
    for path in file_paths:
        if path and Path(path).exists():
            try:
                Path(path).unlink()
                logger.debug(f"Cleaned up temp file: {path}")
            except OSError as e:
                logger.warning(f"Failed to cleanup {path}: {e}")


@celery_app.task(bind=True, max_retries=1)
def process_measurement_task(
    self, 
    image_paths: list[str], 
    marker_size_mm: float, 
    user_id: int, 
    product_id: Optional[int] = None,
    confidence_threshold: float = 0.4  # ← Добавлен параметр с дефолтом
):
    """
    Основная задача обработки измерений.
    
    Статусная машина:
    1. Создаётся запись со статусом PENDING
    2. Обновляется на PROCESSING при старте CV-пайплайна
    3. Финальный статус: COMPLETED / FAILED / NEEDS_REVIEW
    """
    measurement_id: Optional[int] = None
    
    try:
        # === Валидация входных данных ===
        if len(image_paths) != 3:
            raise ValueError("Требуется ровно 3 изображения: front, side, top")

        # === Шаг 1: Создаём запись со статусом PENDING ===
        measurement_id = _create_measurement_record(
            user_id=user_id,
            product_id=product_id,
            initial_dims=(0.0, 0.0, 0.0)
        )

        # === Шаг 2: Обновляем статус на PROCESSING ===
        _update_status_sync(measurement_id, MeasurementStatus.PROCESSING)

        # === Шаг 3: Запускаем CV-пайплайн ===
        model = get_depth_model()
        views = ["front", "side", "top"]
        results: dict[str, dict] = {}
        confidences: list[float] = []

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
        
        # Расчёт отклонения между ракурсами (для verified_ok)
        h_front = results["front"]["height_mm"]
        h_side = results["side"]["height_mm"]
        delta_pct = abs(h_front - h_side) / min(h_front, h_side) * 100 if h_front and h_side else None
        verified_ok = delta_pct <= settings.verify_threshold_pct if delta_pct is not None else None

        # === Шаг 5: Определение финального статуса ===
        if avg_confidence < confidence_threshold:
            final_status = MeasurementStatus.NEEDS_REVIEW
            logger.warning(
                f"Low confidence ({avg_confidence:.2f} < {confidence_threshold}): "
                f"measurement #{measurement_id} marked for review"
            )
        elif verified_ok is False:
            final_status = MeasurementStatus.NEEDS_REVIEW
            logger.warning(
                f"High cross-view deviation ({delta_pct:.1f}%): "
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
            status=final_status,
            delta_pct=delta_pct,
            verified_ok=verified_ok
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
        
    finally:
        # Гарантированная очистка временных файлов
        _cleanup_temp_files(image_paths)