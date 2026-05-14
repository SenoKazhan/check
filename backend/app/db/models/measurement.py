"""
Таблица 3.4: Результаты CV-измерений.
"""
import enum
from sqlalchemy import (
    Column, Integer, Float, Boolean, Text, DateTime, 
    ForeignKey, Index, Enum as SQLEnum  # ← Ключевое: Enum как SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base


class MeasurementStatus(enum.Enum):
    """Статусы обработки измерения."""
    PENDING = "pending"           # Запись создана, задача в очереди
    PROCESSING = "processing"     # Идёт обработка в Celery
    COMPLETED = "completed"       # Успешное завершение
    FAILED = "failed"             # Ошибка обработки
    NEEDS_REVIEW = "needs_review" # Требует ручной проверки (низкий confidence)


class Measurement(Base):
    __tablename__ = "measurements"
    
    __table_args__ = (
        Index("ix_measurements_product", "product_id"),
        Index("ix_measurements_user", "user_id"),
        Index("ix_measurements_measured_at", "measured_at"),
        Index("ix_measurements_status", "status"),  
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
    delta_pct = Column(Float, nullable=True)
    verified_ok = Column(Boolean, nullable=True)
    override_reason = Column(Text, nullable=True)
    
    measured_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="measurements")
    product = relationship("Product", back_populates="measurements")
    packing_items = relationship("PackingItem", back_populates="measurement", lazy="select")
    
    status = Column(
        SQLEnum(
            MeasurementStatus, 
            name="measurement_status",  # Имя ENUM-типа в БД
            create_type=True            # Создать тип при миграции
        ),
        default=MeasurementStatus.PENDING,
        nullable=False,
        server_default=MeasurementStatus.PENDING.value  # Значение по умолчанию в БД
    )
    
