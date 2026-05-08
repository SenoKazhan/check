from typing import Optional
from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qr_code: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    ref_length_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ref_width_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ref_height_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)