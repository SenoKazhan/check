"""Эндпоинт загрузки 3 ракурсов (ТЗ 2.5)."""
import os
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.tasks.cv_pipeline import process_measurement_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = Path("uploads/temp")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png"}
MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 МБ
MIN_WIDTH, MIN_HEIGHT = 640, 480

async def validate_and_save(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(422, f"Недопустимый формат: {file.content_type}. Разрешены JPEG/PNG")
    
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(422, "Файл превышает 10 МБ")
    
    # Простейшая проверка разрешения через OpenCV (ТЗ 2.5)
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise HTTPException(422, "Не удалось декодировать изображение средствами OpenCV")
    h, w = img.shape[:2]
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        raise HTTPException(422, f"Разрешение ниже минимального: {MIN_WIDTH}x{MIN_HEIGHT}. Получено: {w}x{h}")

    ext = ".png" if file.content_type == "image/png" else ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    path = UPLOAD_DIR / filename
    with open(path, "wb") as f:
        f.write(content)
    return str(path)

@router.post("/measure")
async def upload_for_measurement(
    front: UploadFile = File(...),
    side: UploadFile = File(...),
    top: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    paths = []
    try:
        for f in [front, side, top]:
            paths.append(await validate_and_save(f))
    except HTTPException as e:
        for p in paths:
            if os.path.exists(p): os.remove(p)
        raise e

    task = process_images_task.delay(paths)
    logger.info(f"📤 Задача {task.id} отправлена в Celery")
    return {"task_id": task.id, "message": "Изображения приняты. Обработка запущена."}