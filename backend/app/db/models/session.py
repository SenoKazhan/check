"""
Таблицы 3.5, 3.6, 3.7: Упаковка (Сеансы, Товары в сеансе, Результаты).
"""

from sqlalchemy import (
    Column, Integer, Float, Boolean, Text, DateTime, CheckConstraint, 
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..base import Base 


class PackingSession(Base):
    """Таблица 3.5: Сеанс упаковки."""
    __tablename__ = "packing_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'done', 'error')", name="check_session_status"),
        Index("ix_sessions_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Text, nullable=False, default="pending")  # pending, done, error

    # Relationships
    user = relationship("User", back_populates="sessions")
    items = relationship("PackingItem", back_populates="session", lazy="select", cascade="all, delete-orphan")
    results = relationship("PackingResult", back_populates="session", lazy="select", cascade="all, delete-orphan")


class PackingItem(Base):
    """Таблица 3.6: Товары в сеансе (связка)."""
    __tablename__ = "packing_items"
    __table_args__ = (
        Index("ix_items_session", "session_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("packing_sessions.id", ondelete="CASCADE"), nullable=False)
    measurement_id = Column(Integer, ForeignKey("measurements.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    # Relationships
    session = relationship("PackingSession", back_populates="items")
    measurement = relationship("Measurement", back_populates="packing_items")


class PackingResult(Base):
    """Таблица 3.7: Варианты укладки."""
    __tablename__ = "packing_results"
    __table_args__ = (
        Index("ix_results_session", "session_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("packing_sessions.id", ondelete="CASCADE"), nullable=False)
    variant_index = Column(Integer, nullable=False)
    
    box_l_mm = Column(Float, nullable=False)
    box_w_mm = Column(Float, nullable=False)
    box_h_mm = Column(Float, nullable=False)
    box_volume_cm3 = Column(Float, nullable=False)
    
    placements_json = Column(Text, nullable=False)  # JSON координат
    selected = Column(Boolean, nullable=False, default=False)

    # Relationships
    session = relationship("PackingSession", back_populates="results")