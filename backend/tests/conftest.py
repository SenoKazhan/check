import os

# Устанавливаем фейковые переменные окружения ДО импорта приложения,
# чтобы pydantic-settings не выдавал ошибку в CI (где нет .env файла)
os.environ.setdefault("JWT_SECRET_KEY", "test_super_secret_jwt_key_123")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from app.core.config import settings

@pytest.fixture
def mock_image():
    """Создаёт тестовое изображение 640x480"""
    import numpy as np
    return np.zeros((480, 640, 3), dtype=np.uint8)

@pytest.fixture
def sample_items():
    from app.schemas.packing import Item
    return [
        Item(product_id=1, length_mm=100, width_mm=100, height_mm=100, quantity=2)
    ]