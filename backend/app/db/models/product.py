"""
Модель товара (справочник).
"""
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.measurement import Measurement


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qr_code: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    ref_length_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ref_width_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ref_height_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    measurements: Mapped[List["Measurement"]] = relationship(
        "Measurement",
        back_populates="product",
        lazy="select",
        cascade="all, delete-orphan"
    )