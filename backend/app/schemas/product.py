"""Схемы валидации для товаров (Create/Update/Response)."""
from pydantic import BaseModel, Field
from typing import Optional

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    qr_code: Optional[str] = Field(None, max_length=255)
    ref_length_mm: Optional[float] = Field(None, gt=0)
    ref_width_mm: Optional[float] = Field(None, gt=0)
    ref_height_mm: Optional[float] = Field(None, gt=0)
    notes: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    qr_code: Optional[str] = Field(None, max_length=255)
    ref_length_mm: Optional[float] = Field(None, gt=0)
    ref_width_mm: Optional[float] = Field(None, gt=0)
    ref_height_mm: Optional[float] = Field(None, gt=0)
    notes: Optional[str] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    qr_code: Optional[str]
    ref_length_mm: Optional[float]
    ref_width_mm: Optional[float]
    ref_height_mm: Optional[float]
    notes: Optional[str]

    class Config:
        from_attributes = True