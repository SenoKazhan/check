"""
Схемы данных для модуля трёхмерной упаковки.
Соответствует ТЗ, раздел 3.1.
"""

from pydantic import BaseModel, Field
from typing import List


class Item(BaseModel):
    """
    Описание одного вида товара для алгоритма упаковки.
    """
    product_id: int = Field(..., description="Идентификатор товара в справочнике")
    length_mm: float = Field(..., gt=0, description="Длина в мм")
    width_mm: float = Field(..., gt=0, description="Ширина в мм")
    height_mm: float = Field(..., gt=0, description="Высота в мм")
    quantity: int = Field(default=1, ge=1, description="Количество единиц данного вида")


class Placement(BaseModel):
    """
    Положение одного экземпляра товара внутри коробки.
    """
    item_id: int = Field(..., description="Идентификатор товара (product_id)")
    x_mm: float = Field(..., description="Координата X левого нижнего угла (мм)")
    y_mm: float = Field(..., description="Координата Y левого нижнего угла (мм)")
    z_mm: float = Field(..., description="Координата Z левого нижнего угла (мм)")
    rotated: bool = Field(False, description="Поворот на 90° вокруг оси Z")


class PackResult(BaseModel):
    """
    Один вариант упаковки (коробка + размещения товаров).
    """
    box_l_mm: float = Field(..., description="Длина коробки в мм")
    box_w_mm: float = Field(..., description="Ширина коробки в мм")
    box_h_mm: float = Field(..., description="Высота коробки в мм")
    box_volume_cm3: float = Field(..., description="Объём коробки в см³")
    placements: List[Placement] = Field(..., description="Список размещений всех экземпляров")