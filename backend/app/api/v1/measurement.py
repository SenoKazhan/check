"""
API эндпоинты для модуля измерений.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
import tempfile
import os
from pathlib import Path
import uuid

from app.tasks.cv_pipeline import process_measurement_task
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/measurements", tags=["Измерения"])

@router.post("/start")
async def start_measurement(
    files: List[UploadFile] = File(..., min_items=3, max_items=3, description="3 изображения: front, side, top"),
    marker_size_mm: float = 50.0,
    product_id: int = None,
    # current_user: dict = Depends(get_current_user) # Получаем ID пользователя из токена
):
    """
    Запуск задачи измерения габаритов.
    Принимает 3 файла, сохраняет во временную директорию и запускает Celery-задачу.
    """
    user_id = 1 
    if len(files) != 3:
        raise HTTPException(400, "Требуется ровно 3 файла: front, side, top")
    
    # Валидация MIME
    allowed_types = ["image/jpeg", "image/png"]
    for f in files:
        if f.content_type not in allowed_types:
            raise HTTPException(422, f"Недопустимый формат: {f.content_type}. Разрешены: {allowed_types}")
    
    # Сохраняем во временные файлы для Celery
    temp_dir = tempfile.mkdtemp()
    temp_paths = []
    
    try:
        for i, f in enumerate(files):
            # Генерируем уникальное имя файла
            file_extension = f.filename.split(".")[-1] if "." in f.filename else "jpg"
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            path = os.path.join(temp_dir, unique_filename)
            
            with open(path, "wb") as out:
                content = await f.read()
                out.write(content)
            temp_paths.append(path)
        
        # Запуск асинхронной задачи Celery
        # Передаём пути к файлам, размер маркера и ID пользователя
        task = process_measurement_task.delay(
            temp_paths, 
            marker_size_mm, 
            user_id=user_id,
            # user_id=current_user["id"],
            product_id=product_id
        )
        
        return {
            "task_id": task.id, 
            "status": "processing",
            "message": "Задача измерения запущена. Используйте task_id для проверки статуса."
        }
        
    except Exception as e:
        # Очистка временных файлов в случае ошибки
        for p in temp_paths:
            if os.path.exists(p):
                os.remove(p)
        raise HTTPException(500, f"Ошибка при запуске задачи: {str(e)}")