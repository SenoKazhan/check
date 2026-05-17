"""
Модуль верификации результатов измерений.
Сравнивает измеренные габариты с эталонными значениями из справочника.
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VerifyResult:
    ok: Optional[bool]      # True=совпадает, False=расхождение, None=нет эталона
    overridden: bool = False
    delta_pct: Optional[float] = None
    details: Optional[Dict[str, float]] = None  # отклонения по осям

class DimensionVerifier:
    """Верификатор габаритов: сравнение с эталоном и оценка достоверности."""

    def __init__(self, threshold_pct: float = 10.0):
        self.threshold_pct = threshold_pct

    def verify(
        self,
        measured: Dict[str, float],
        reference: Optional[Dict[str, Optional[float]]] = None,
        confidence: float = 1.0
    ) -> VerifyResult:
        """
        Выполняет верификацию измеренных габаритов.
        measured: {"length_mm": ..., "width_mm": ..., "height_mm": ...}
        reference: {"ref_length_mm": ..., ...} или None
        """
        if not reference or all(v is None for v in reference.values() if v is not None):
            return VerifyResult(ok=None, delta_pct=None, details=None)

        deltas = {}
        for axis in ["length_mm", "width_mm", "height_mm"]:
            ref_key = f"ref_{axis}"
            ref_val = reference.get(ref_key)
            meas_val = measured.get(axis)
            if ref_val and meas_val and ref_val > 0:
                dev = abs(meas_val - ref_val) / ref_val * 100
                deltas[axis] = round(dev, 2)

        if not deltas:
            return VerifyResult(ok=None, delta_pct=None, details=None)

        max_delta = max(deltas.values())
        is_ok = max_delta <= self.threshold_pct

        if confidence < 0.4:
            logger.warning(f"Низкая уверенность модели: {confidence:.2f}")

        logger.info(f"Верификация: max_delta={max_delta:.1f}%, ok={is_ok}, conf={confidence:.2f}")
        return VerifyResult(ok=is_ok, delta_pct=max_delta, details=deltas)