# backend/app/cv/qr_scanner.py
import asyncio
import logging
from typing import Any, Dict, Optional
import numpy as np
from pyzbar.pyzbar import ZBarSymbol, decode

logger = logging.getLogger(__name__)

class QRScanner:
    """Интеллектуальный сканер кодов для складской системы."""

    async def decode_image(self, image_bgr: np.ndarray) -> Optional[str]:
        """
        Декодирует QR-код или штрихкод. 
        Пробует разные типы последовательно, чтобы избежать крашей от плохих данных.
        """
        
        # Список типов для попытки декодирования
        # Используем только те символы, которые гарантированно есть в стандартной сборке libzbar
        symbol_groups = [
            [ZBarSymbol.QRCODE],
            [ZBarSymbol.EAN13, ZBarSymbol.EAN8, ZBarSymbol.UPCA, ZBarSymbol.UPCE],
            [ZBarSymbol.CODE128, ZBarSymbol.CODE39, ZBarSymbol.CODE93, ZBarSymbol.I25],
        ]

        for symbols in symbol_groups:
            try:
                decoded_objects = decode(image_bgr, symbols=symbols)
                if decoded_objects:
                    return decoded_objects[0].data.decode('utf-8')
            except Exception as e:
                # Логируем только если это критично, но не прерываем цикл
                logger.debug(f"Не удалось декодировать группу {symbols}: {e}")
                continue
                
        return None

    async def lookup_product(self, qr_string: str, db_session) -> Optional[Dict[str, Any]]:
        """Ищет товар в справочнике по декодированной строке."""
        from sqlalchemy import select
        from app.db.models.product import Product

        try:
            stmt = select(Product).where(Product.qr_code == qr_string)
            result = await db_session.execute(stmt)
            product = result.scalar_one_or_none()

            if product:
                logger.info(f"Товар найден по коду: {product.name} (ID={product.id})")
                return {
                    "id": product.id,
                    "name": product.name,
                    "ref_length_mm": product.ref_length_mm,
                    "ref_width_mm": product.ref_width_mm,
                    "ref_height_mm": product.ref_height_mm,
                    "notes": product.notes
                }
            logger.warning(f"Товар с кодом '{qr_string}' не найден в справочнике")
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска товара: {e}")
            return None

    async def scan_and_lookup(self, image_bgr: np.ndarray, db_session) -> Dict[str, Any]:
        """Оркестрирующий метод: сканирует изображение и ищет товар."""
        qr_string = await self.decode_image(image_bgr)
        if not qr_string:
            return {"qr_string": None, "product": None, "has_reference_dims": False}

        product = await self.lookup_product(qr_string, db_session)
        has_ref = bool(product and any(
            product.get(k) for k in ("ref_length_mm", "ref_width_mm", "ref_height_mm")
        ))

        return {
            "qr_string": qr_string,
            "product": product,
            "has_reference_dims": has_ref
        }