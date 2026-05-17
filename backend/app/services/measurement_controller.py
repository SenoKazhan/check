"""
Модуль контроллера процесса измерения.
Реализует бизнес-логику маршрутизации рабочего процесса.
"""
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class RoutingAction(str, Enum):
    USE_REFERENCE = "use_reference"      # Товар найден, эталон есть
    MEASURE = "measure"                  # Товар найден, эталона нет
    NO_PRODUCT_MEASURE = "no_product_measure" # Товар не найден -> измерение без привязки
    REPEAT_MEASUREMENT = "repeat"        # Верификация не прошла
    CONFIRM_FORCE = "confirm_force"      # Принудительное подтверждение

class MeasurementController:
    """Оркестратор рабочего процесса измерения и упаковки."""

    def __init__(self, verify_threshold_pct: float = 10.0):
        self.verify_threshold_pct = verify_threshold_pct

    def route_after_qr(self, scan_result: Dict[str, Any]) -> RoutingAction:
        """Определяет следующий шаг после сканирования QR."""
        product = scan_result.get("product")
        has_ref = scan_result.get("has_reference_dims", False)

        if product and has_ref:
            return RoutingAction.USE_REFERENCE
        elif product and not has_ref:
            return RoutingAction.MEASURE
        return RoutingAction.NO_PRODUCT_MEASURE

    def handle_verify_result(self, verify_ok: Optional[bool], delta_pct: Optional[float]) -> RoutingAction:
        """Реакция на результат верификации."""
        if verify_ok is None or verify_ok is True:
            return RoutingAction.CONFIRM_FORCE
        
        logger.warning(f"Расхождение {delta_pct:.1f}% превышает порог {self.verify_threshold_pct}%")
        return RoutingAction.REPEAT_MEASUREMENT

    def prepare_session_item(self, product_id: Optional[int], measurement_id: int, quantity: int = 1) -> Dict[str, Any]:
        """Формирует данные для добавления товара в сессию упаковки."""
        return {
            "product_id": product_id,
            "measurement_id": measurement_id,
            "quantity": quantity
        }