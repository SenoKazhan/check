"""
Модуль QR-обработчика.
Декодирует QR-коды с изображений и выполняет поиск товаров в справочнике.
"""
import asyncio
import logging
from typing import Any, Dict, Optional

import numpy as np
from pyzbar.pyzbar import ZBarSymbol, decode

logger = logging.getLogger(__name__)


class QRScanner:
    """Интеллектуальный сканер QR-кодов для складской системы."""

    async def decode_image(self, image_bgr: np.ndarray) -> Optional[str]:
        """
        Декодирует QR-код из изображения BGR (выполняется в пуле потоков).
        Возвращает строку содержимого или None.
        """
        def _decode_sync():
            try:
                decoded = decode(image_bgr, symbols=[ZBarSymbol.QRCODE])
                return decoded[0].data.decode('utf-8') if decoded else None
            except Exception as e:
                logger.error(f"Ошибка декодирования QR-кода: {e}")
                return None

        return await asyncio.to_thread(_decode_sync)

    async def lookup_product(self, qr_string: str, db_session) -> Optional[Dict[str, Any]]:
        """Ищет товар в справочнике по декодированной строке QR."""
        from sqlalchemy import select

        from app.db.models.product import Product

        try:
            stmt = select(Product).where(Product.qr_code == qr_string)
            result = await db_session.execute(stmt)
            product = result.scalar_one_or_none()

            if product:
                logger.info(
                    f"Товар найден по QR: {product.name} (ID={product.id})")
                return {
                    "id": product.id,
                    "name": product.name,
                    "ref_length_mm": product.ref_length_mm,
                    "ref_width_mm": product.ref_width_mm,
                    "ref_height_mm": product.ref_height_mm,
                    "notes": product.notes
                }
            logger.warning(f"Товар с QR '{qr_string}' не найден в справочнике")
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска товара по QR: {e}")
            return None

    async def scan_and_lookup(self, image_bgr: np.ndarray, db_session) -> Dict[str, Any]:
        """Оркестрирующий метод: сканирует изображение и ищет товар."""
        qr_string = await self.decode_image(image_bgr)
        if not qr_string:
            return {"qr_string": None, "product": None, "has_reference_dims": False}

        product = await self.lookup_product(qr_string, db_session)
        has_ref = bool(product and any(product.get(k)
                       for k in ("ref_length_mm", "ref_width_mm", "ref_height_mm")))

        return {
            "qr_string": qr_string,
            "product": product,
            "has_reference_dims": has_ref
        }
