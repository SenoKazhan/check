"""API эндпоинты для модуля измерений."""
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.models import Measurement
from app.db.models.user import User
from app.db.session import get_db
from app.tasks.cv_pipeline import process_measurement_task
from app.cv.qr_scanner import QRScanner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/measurements", tags=["Измерения"])

ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024
MIN_WIDTH, MIN_HEIGHT = settings.min_image_width, settings.min_image_height

def _validate_image(content: bytes) -> tuple[int, int]:
    try:
        img_array = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("Не удалось декодировать изображение")
        h, w = img.shape[:2]
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            raise ValueError(f"Разрешение {w}x{h} ниже минимального {MIN_WIDTH}x{MIN_HEIGHT}")
        return w, h
    except Exception as e:
        raise HTTPException(422, f"Ошибка валидации изображения: {str(e)}")

async def _save_file_secure(file: UploadFile, upload_dir: Path) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(422, f"Недопустимый формат: {file.content_type}")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(422, f"Файл превышает лимит {settings.max_upload_size_mb} МБ")
    _validate_image(content)

    file_extension = Path(file.filename).suffix.lower() or ".jpg"
    if file_extension not in [".jpg", ".jpeg", ".png"]:
        file_extension = ".jpg"
    
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = upload_dir / unique_filename

    with open(file_path, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    return str(file_path)

@router.post("/scan")
async def scan_qr(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    content = await file.read()
    img_array = np.frombuffer(content, np.uint8)
    img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(422, "Не удалось декодировать изображение")
    scanner = QRScanner()
    result = await scanner.scan_and_lookup(img_bgr, db)
    return result

@router.post("/start")
async def start_measurement(
    files: List[UploadFile] = File(..., min_items=3, max_items=3),
    marker_size_mm: float = 50.0,
    product_id: Optional[int] = None,
    manual_roi: Optional[str] = None,  # Формат: "x1,y1,x2,y2"
    current_user: User = Depends(get_current_user)
):
    if len(files) != 3:
        raise HTTPException(400, detail="Требуется ровно 3 файла: front, side, top")

    upload_dir = Path("/app/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = []
    roi_tuple: Optional[Tuple[int, int, int, int]] = None
    
    # Парсинг ROI
    if manual_roi:
        try:
            coords = [int(x.strip()) for x in manual_roi.split(",")]
            if len(coords) == 4:
                roi_tuple = tuple(coords)
                logger.info(f"Parsed manual ROI: {roi_tuple}")
            else:
                logger.warning(f"Invalid ROI coordinates count: {len(coords)}")
        except ValueError:
            logger.warning(f"Failed to parse manual_roi string: {manual_roi}")

    try:
        for file in files:
            path = await _save_file_secure(file, upload_dir)
            saved_paths.append(path)

        task = process_measurement_task.delay(
            image_paths=saved_paths,
            marker_size_mm=marker_size_mm,
            user_id=current_user.id,
            product_id=product_id,
            manual_roi=roi_tuple, # <-- Передача кортежа в Celery
        )

        logger.info(f"Задача измерения запущена: task_id={task.id}, user_id={current_user.id}, roi={roi_tuple}")
        return {"task_id": task.id, "status": "processing", "message": "Задача измерения запущена."}

    except HTTPException:
        for path in saved_paths:
            if os.path.exists(path): os.remove(path)
        raise
    except Exception as e:
        logger.error(f"Ошибка при запуске измерения: {e}", exc_info=True)
        for path in saved_paths:
            if os.path.exists(path): os.remove(path)
        raise HTTPException(500, detail="Внутренняя ошибка сервера при обработке запроса")

@router.get("/tasks/{task_id}")
async def get_task_result(task_id: str):
    from celery.result import AsyncResult
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "state": result.state}
    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.info) if result.info else "Неизвестная ошибка"
    return response