# app/api/v1/measurement.py
"""API эндпоинты для модуля измерений."""
from app.cv.qr_scanner import QRScanner
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from app.db.enums import MeasurementStatus
from celery.result import AsyncResult
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.models import Measurement
from app.db.session import get_db
from app.tasks.cv_pipeline import process_measurement_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/measurements", tags=["Измерения"])

# Константы валидации
ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024  # из config.py
MIN_WIDTH, MIN_HEIGHT = settings.min_image_width, settings.min_image_height


def _cleanup_files(file_paths: List[str]) -> None:
    """Фоновая очистка временных файлов."""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Удалён временный файл: {path}")
        except OSError as e:
            logger.warning(f"Не удалось удалить файл {path}: {e}")


def _validate_image(content: bytes) -> tuple[int, int]:
    """
    Валидация изображения: декодирование и проверка разрешения.
    Returns: (width, height) или выбрасывает HTTPException.
    """
    try:
        img_array = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("Не удалось декодировать изображение")
        h, w = img.shape[:2]
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            raise ValueError(
                f"Разрешение {w}x{h} ниже минимального {MIN_WIDTH}x{MIN_HEIGHT}")
        return w, h
    except Exception as e:
        raise HTTPException(422, f"Ошибка валидации изображения: {str(e)}")


async def _save_file_secure(file: UploadFile, upload_dir: Path) -> str:
    """
    Безопасное сохранение файла с валидацией.
    Returns: путь к сохранённому файлу.
    """
    # Проверка MIME-типа
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(422, f"Недопустимый формат: {file.content_type}")

    # Чтение и проверка размера
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            422, f"Файл превышает лимит {settings.max_upload_size_mb} МБ")

    # Валидация изображения
    _validate_image(content)

    # Сохранение
    file_extension = Path(file.filename).suffix.lower() or ".jpg"
    if file_extension not in [".jpg", ".jpeg", ".png"]:
        file_extension = ".jpg"

    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = upload_dir / unique_filename

    file_path.write_bytes(content)
    return str(file_path)


@router.post("/scan")
async def scan_qr(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Декодирует QR-код и ищет товар в справочнике."""
    from app.cv.qr_scanner import QRScanner
    import numpy as np
    import cv2

    content = await file.read()
    img_array = np.frombuffer(content, np.uint8)
    img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    if img_bgr is None:
        raise HTTPException(422, "Не удалось декодировать изображение")

    scanner = QRScanner()
    result = await scanner.scan_and_lookup(img_bgr, db)

    if result["product"] is None:
        return {
            "status": "not_found",
            "qr_string": result["qr_string"],
            "message": "QR-код распознан, но товар не найден"
        }

    return {
        "status": "ok",
        "product": result["product"],
        "has_reference_dims": result["has_reference_dims"]
    }


@router.post("/start")
async def start_measurement(
    files: List[UploadFile] = File(..., min_items=3, max_items=3,
                                   description="3 изображения: front, side, top"),
    marker_size_mm: float = 50.0,
    product_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    Запуск задачи измерения габаритов.
    Принимает 3 файла, валидирует, сохраняет и запускает Celery-задачу.
    """
    if len(files) != 3:
        raise HTTPException(
            400, detail="Требуется ровно 3 файла: front, side, top")

    # Создаём директорию для загрузки (если используется общий volume)
    upload_dir = Path(settings.upload_dir if hasattr(
        settings, 'upload_dir') else "/app/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    try:
        # Последовательная валидация и сохранение
        for file in files:
            path = await _save_file_secure(file, upload_dir)
            saved_paths.append(path)

        task = process_measurement_task.delay(
            image_paths=saved_paths,
            marker_size_mm=marker_size_mm,
            user_id=current_user["id"],
            product_id=product_id
        )

        logger.info(
            f"Задача измерения запущена: task_id={task.id}, user_id={current_user['id']}")

        return {
            "task_id": task.id,
            "status": "processing",
            "message": "Задача измерения запущена. Используйте task_id для проверки статуса."
        }

    except HTTPException:

        _cleanup_files(saved_paths)
        raise
    except Exception as e:
        logger.error(f"Ошибка при запуске измерения: {e}", exc_info=True)
        _cleanup_files(saved_paths)
        raise HTTPException(
            500, detail="Внутренняя ошибка сервера при обработке запроса")
    finally:

        if background_tasks and saved_paths:
            background_tasks.add_task(_cleanup_files, saved_paths)


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Получение статуса задачи измерения.
    """

    result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "status": result.state,
    }

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(
            result.info) if result.info else "Неизвестная ошибка"

    return response


@router.get("/{measurement_id}")
async def get_measurement(
    measurement_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение измерения с текущим статусом."""
    result = await db.execute(
        select(Measurement).where(Measurement.id == measurement_id)
    )
    measurement = result.scalar_one_or_none()
    if not measurement:
        raise HTTPException(404, "Измерение не найдено")
    return measurement


@router.get("/{measurement_id}/status")
async def get_measurement_status(
    measurement_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Measurement.status).where(Measurement.id == measurement_id)
    )
    status = result.scalar_one_or_none()

    if not status:
        raise HTTPException(404, detail="Измерение не найдено")

    return {"measurement_id": measurement_id, "status": status}


@router.get("/user/{user_id}")
async def get_user_measurements(
    user_id: int,
    status: MeasurementStatus | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Список измерений пользователя с фильтрацией по статусу."""
    query = select(Measurement).where(Measurement.user_id == user_id)

    if status:
        query = query.where(Measurement.status == status)

    query = query.order_by(Measurement.measured_at.desc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


qr_scanner = QRScanner()


@router.post("/scan")
async def scan_qr(file: UploadFile, db: AsyncSession = Depends(get_db)):
    img_bytes = await file.read()
    img_np = np.frombuffer(img_bytes, np.uint8)
    img_bgr = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
    return await qr_scanner.scan_and_lookup(img_bgr, db)
