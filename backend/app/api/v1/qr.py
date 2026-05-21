# backend/app/api/v1/qr.py
import logging

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.cv.qr_scanner import QRScanner
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qr", tags=["QR Scanner"])

@router.post("/decode")
async def decode_qr_from_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Декодирует QR-код или штрихкод из загруженного изображения.
    Возвращает содержимое кода и данные товара, если он найден в справочнике.
    """
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image_bgr is None:
            logger.error("Не удалось декодировать изображение")
            raise HTTPException(400, "Не удалось прочитать изображение")
        
        logger.info(f"Размер изображения: {image_bgr.shape}")
        
        # Используем существующий сканер, который уже поддерживает и QR, и штрихкоды
        scanner = QRScanner()
        result = await scanner.scan_and_lookup(image_bgr, db)
        
        logger.info(f"Результат сканирования: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при декодировании QR: {e}", exc_info=True)
        raise HTTPException(500, f"Ошибка обработки: {str(e)}")