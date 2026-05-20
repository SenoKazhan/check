# backend/tests/conftest.py
"""
Фикстуры pytest для интеграционных тестов.
Минималистичный подход: мокируем внешние зависимости, используем чистую БД.
"""
import os
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base

# URL тестовой БД (localhost для Docker Desktop на Windows)
TEST_DB_URL = "postgresql+asyncpg://app_user:dev_password@localhost:5432/warehouse_test"
SYNC_TEST_DB_URL = TEST_DB_URL.replace("+asyncpg", "")


@pytest.fixture(scope="session")
def event_loop_policy():
    """Windows-compatible event loop policy."""
    return asyncio.WindowsSelectorEventLoopPolicy()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Создаёт чистую схему тестовой БД.
    Не использует Alembic для скорости и надёжности.
    """
    # Проверяем подключение
    try:
        check_engine = create_engine(
            SYNC_TEST_DB_URL.replace("warehouse_test", "postgres"),
            pool_pre_ping=True,
            isolation_level="AUTOCOMMIT"
        )
        with check_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = 'warehouse_test'")
            ).scalar()
            if not result:
                conn.execute(text("CREATE DATABASE warehouse_test"))
                conn.execute(text("GRANT ALL ON DATABASE warehouse_test TO app_user"))
        check_engine.dispose()
    except Exception as e:
        pytest.fail(f"PostgreSQL connection failed: {e}")

    # Создаём схему напрямую
    engine = create_engine(SYNC_TEST_DB_URL, pool_pre_ping=True)
    
    with engine.begin() as conn:
        # Полная очистка
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO app_user"))
        
        # ENUM тип
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE measurement_status_enum AS ENUM (
                    'pending', 'processing', 'completed', 'failed', 'needs_review'
                );
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Таблицы с checkfirst=True
        Base.metadata.create_all(conn, checkfirst=True)
    
    engine.dispose()
    yield


@pytest.fixture
async def db_session():
    """Асинхронная сессия с авто-откатом."""
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    session = async_session()
    
    try:
        yield session
        await session.rollback()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


@pytest.fixture
def client():
    """TestClient для интеграционных тестов."""
    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Моки внешних зависимостей (КРИТИЧНО ДЛЯ ИНТЕГРАЦИОННЫХ ТЕСТОВ)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_redis():
    """
    Патчит redis_client во ВСЕХ модулях.
    Возвращает AsyncMock для корректной работы с await.
    """
    mock_client = AsyncMock()
    mock_client.get.return_value = None
    mock_client.incr.return_value = 1
    mock_client.expire.return_value = True
    mock_client.setex.return_value = True
    
    mock_pipe = AsyncMock()
    mock_pipe.execute.return_value = [1, True]
    mock_client.pipeline.return_value = mock_pipe
    
    patches = [
        patch('app.core.redis.redis_client', mock_client),
        patch('app.services.rate_limiting_service.redis_client', mock_client),
    ]
    
    for p in patches:
        p.start()
    
    yield mock_client
    
    for p in patches:
        p.stop()


@pytest.fixture
def mock_rate_limit():
    """Полностью отключает rate limiting в зависимостях."""
    with patch('app.api.dependencies.check_auth_rate_limit', return_value=None):
        with patch('app.services.rate_limiting_service.RateLimitingService.check_auth_rate_limit', return_value=None):
            yield


@pytest.fixture
def mock_settings():
    """Мок настроек для unit-тестов AuthManager."""
    mock = MagicMock()
    mock.jwt_secret_key = "test-secret-key"
    mock.jwt_algorithm = "HS256"
    mock.access_token_expire_minutes = 30
    mock.bcrypt_cost = 4
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# Остальные фикстуры (без изменений)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_current_user():
    with patch('app.api.dependencies.get_current_user') as mock:
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.login = "test_user"
        mock_user.role = "admin"
        mock.return_value = mock_user
        yield mock


@pytest.fixture
def mock_depth_model():
    with patch('app.tasks.cv_pipeline.get_cached_depth_model') as mock:
        model_mock = MagicMock()
        model_mock.estimate.return_value = MagicMock()
        mock.return_value = model_mock
        yield model_mock


@pytest.fixture
def mock_aruco_detection():
    with patch('app.cv.aruco_measure.detect_aruco') as mock:
        mock.return_value = (
            [[100, 100], [200, 100], [200, 200], [100, 200]],
            42,
            "DICT_4X4_50"
        )
        yield mock


@pytest.fixture
def test_user_data():
    return {"login": "test_user", "password": "testpass123", "role": "worker"}


@pytest.fixture
def test_admin_data():
    return {"login": "admin_test", "password": "adminpass456", "role": "admin"}


@pytest.fixture
def test_product_data():
    return {
        "name": "Тестовая коробка",
        "qr_code": "TEST-QR-001",
        "ref_length_mm": 200.0,
        "ref_width_mm": 150.0,
        "ref_height_mm": 100.0,
        "notes": "Создано тестом"
    }