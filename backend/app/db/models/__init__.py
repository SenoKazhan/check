"""
Модели SQLAlchemy для PostgreSQL.
Соответствует ТЗ, раздел 3.3, таблицы 3.2–3.7.
"""
from ..base import Base  # Ищет внутри папки models/
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, CheckConstraint,
    ForeignKey, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase, relationship


from .user import User
from .product import Product

from .measurement import Measurement
from .session import PackingSession

class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class User(Base):
    """Таблица 3.2: Учётные записи работников."""
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('worker', 'admin')", name="check_role"),
        Index("ix_users_login", "login", unique=True),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    login = Column(String(64), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(10), nullable=False, default="worker")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    measurements = relationship(
        "Measurement", back_populates="user", lazy="select")
    sessions = relationship(
        "PackingSession", back_populates="user", lazy="select")


class Product(Base):
    """Таблица 3.3: Справочник товаров."""
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_qr", "qr_code", unique=True,
              postgresql_where="qr_code IS NOT NULL"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    qr_code = Column(String(255), unique=True, nullable=True)
    ref_length_mm = Column(Float, nullable=True)
    ref_width_mm = Column(Float, nullable=True)
    ref_height_mm = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    measurements = relationship(
        "Measurement", back_populates="product", lazy="select")


class Measurement(Base):
    """Таблица 3.4: Результаты CV-измерений."""
    __tablename__ = "measurements"
    __table_args__ = (
        Index("ix_measurements_product", "product_id"),
        Index("ix_measurements_user", "user_id"),
        Index("ix_measurements_measured_at", "measured_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey(
        "products.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    length_mm = Column(Float, nullable=False)
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    delta_pct = Column(Float, nullable=True)
    verified_ok = Column(Boolean, nullable=True)
    override_reason = Column(Text, nullable=True)
    measured_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="measurements")
    product = relationship("Product", back_populates="measurements")
    packing_items = relationship(
        "PackingItem", back_populates="measurement", lazy="select")


class PackingSession(Base):
    """Таблица 3.5: Сеанс упаковки."""
    __tablename__ = "packing_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'done', 'error')",
                        name="check_session_status"),
        Index("ix_sessions_user", "user_id"),
        Index("ix_sessions_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey(
        "users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(10), nullable=False, default="pending")

    # Relationships
    user = relationship("User", back_populates="sessions")
    items = relationship("PackingItem", back_populates="session",
                         lazy="select", cascade="all, delete-orphan")
    results = relationship("PackingResult", back_populates="session",
                           lazy="select", cascade="all, delete-orphan")


class PackingItem(Base):
    """Таблица 3.6: Товары в сеансе (связь многие-ко-многим)."""
    __tablename__ = "packing_items"
    __table_args__ = (
        Index("ix_items_session", "session_id"),
        Index("ix_items_measurement", "measurement_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey(
        "packing_sessions.id", ondelete="CASCADE"), nullable=False)
    measurement_id = Column(Integer, ForeignKey(
        "measurements.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)

    # Relationships
    session = relationship("PackingSession", back_populates="items")
    measurement = relationship("Measurement", back_populates="packing_items")


class PackingResult(Base):
    """Таблица 3.7: Варианты укладки."""
    __tablename__ = "packing_results"
    __table_args__ = (
        Index("ix_results_session", "session_id"),
        Index("ix_results_selected", "session_id",
              "selected", postgresql_where="selected = true"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey(
        "packing_sessions.id", ondelete="CASCADE"), nullable=False)
    variant_index = Column(Integer, nullable=False)
    box_l_mm = Column(Float, nullable=False)
    box_w_mm = Column(Float, nullable=False)
    box_h_mm = Column(Float, nullable=False)
    box_volume_cm3 = Column(Float, nullable=False)
    placements_json = Column(Text, nullable=False)  # JSON-массив координат
    selected = Column(Boolean, nullable=False, default=False)

    # Relationships
    session = relationship("PackingSession", back_populates="results")
