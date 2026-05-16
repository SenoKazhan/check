"""
Pydantic-схемы для API настроек.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Any, Optional


class SettingResponse(BaseModel):
    """Ответ с информацией о настройке."""
    key: str = Field(..., description="Идентификатор настройки")
    label: str = Field(..., description="Человекочитаемое название")
    type: Literal["boolean", "number", "string"] = Field(..., description="Тип значения для UI")
    value: Any = Field(..., description="Текущее значение в нативном типе")
    display_value: Any = Field(..., description="Значение для отображения (с учётом multiplier)")
    unit: str = Field("", description="Единица измерения для отображения")
    description: str = Field("", description="Подсказка для пользователя")
    min: Optional[float] = Field(None, description="Минимальное допустимое значение")
    max: Optional[float] = Field(None, description="Максимальное допустимое значение")
    step: Optional[float] = Field(None, description="Шаг изменения для input type=number")

    class Config:
        from_attributes = True


class SettingUpdateRequest(BaseModel):
    """Запрос на обновление настройки."""
    value: Any = Field(..., description="Новое значение")
    change_reason: Optional[str] = Field(None, max_length=255, description="Причина изменения (для аудита)")

    @field_validator("value")
    @classmethod
    def validate_value_type(cls, v):
        """Базовая валидация типа (детальная — в сервисе)."""
        if isinstance(v, bool | int | float | str):
            return v
        raise ValueError("Неподдерживаемый тип значения")


class SettingsGroupResponse(BaseModel):
    """Группированные настройки для отображения в табах."""
    groups: dict[
        Literal["computer_vision", "verification", "uploads", "packing"],
        list[SettingResponse]
    ] = Field(..., description="Настройки, сгруппированные по категориям")