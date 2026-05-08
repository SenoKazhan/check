"""
Таблица 3.4: Результаты CV-измерений.
"""

from sqlalchemy import (
    Column, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base  # Импортируем Base из соседнего файла base.py (или общего)


class Measurement(Base):
    __tablename__ = "measurements"
    
    # Индексы для ускорения поиска
    __table_args__ = (
        Index("ix_measurements_product", "product_id"),
        Index("ix_measurements_user", "user_id"),
        Index("ix_measurements_measured_at", "measured_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Связи
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Результаты измерений
    length_mm = Column(Float, nullable=False)
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    
    # Верификация
    delta_pct = Column(Float, nullable=True)  # % отклонения
    verified_ok = Column(Boolean, nullable=True)  # True/False/None
    override_reason = Column(Text, nullable=True)  # Если подтвердили принудительно
    
    measured_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="measurements")
    product = relationship("Product", back_populates="measurements")
    
    # Связь с товарами в сеансе
    packing_items = relationship("PackingItem", back_populates="measurement", lazy="select")