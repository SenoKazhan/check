# backend/app/db/models/__init__.py
from ..base import Base  # Импорт из родительской папки (db), файла base.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, CheckConstraint, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

# Импортируйте все модели здесь, чтобы Alembic их увидел
from .user import User
from .product import Product
from .measurement import Measurement
from .session import PackingSession, PackingItem, PackingResult

__all__ = ["Base", "User", "Product", "Measurement", "PackingSession", "PackingItem", "PackingResult"]