"""
Схемы данных для модуля измерений.
Соответствует ТЗ, раздел 3.1 (DTO).
"""

from pydantic import BaseModel, Field
from typing import Optional, List

from enum import Enum
from pydantic import BaseModel, Field

class MeasurementStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    
class MeasureResult(BaseModel):
    """Результат CV-измерения габаритов."""
    length_mm: float = Field(..., gt=0, description="Длина в мм")
    width_mm: float = Field(..., gt=0, description="Ширина в мм")
    height_mm: float = Field(..., gt=0, description="Высота в мм")
    confidence: float = Field(..., ge=0, le=1, description="Показатель однородности карты глубины")
    status: MeasurementStatus = Field(default=MeasurementStatus.PENDING)

class VerifyResult(BaseModel):
    """Результат верификации измерения."""
    ok: Optional[bool] = Field(None, description="True если соответствует эталону, None если эталона нет")
    overridden: bool = Field(False, description="Принудительное подтверждение оператором")
    delta_pct: Optional[float] = Field(None, description="Максимальное отклонение в %")
    details: Optional[dict[str, float]] = Field(None, description="Отклонения по осям")


class MeasurementCreate(BaseModel):
    """Запрос на создание записи измерения (внутренняя структура)."""
    product_id: Optional[int] = None
    user_id: int
    measure_result: MeasureResult
    verify_result: VerifyResult


class MeasurementResponse(BaseModel):
    """Ответ API с данными измерения."""
    id: int
    product_id: Optional[int]
    length_mm: float
    width_mm: float
    height_mm: float
    verified_ok: Optional[bool]
    measured_at: str  

    class Config:
        from_attributes = True