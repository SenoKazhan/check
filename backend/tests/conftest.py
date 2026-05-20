# backend/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
TEST_DB_URL = "postgresql+asyncpg://app_user:dev_password@127.0.0.1:5432/warehouse_test"
settings.database_url = TEST_DB_URL

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.main import app

@pytest.fixture
def mock_settings():
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.jwt_secret_key = "test-secret-key"
    mock.jwt_algorithm = "HS256"
    mock.access_token_expire_minutes = 30
    mock.bcrypt_cost = 4
    return mock

@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.WindowsSelectorEventLoopPolicy()

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()
    
    try:
        await session.execute(text("TRUNCATE TABLE users CASCADE"))
        await session.execute(text("TRUNCATE TABLE products CASCADE"))
        await session.execute(text("TRUNCATE TABLE measurements CASCADE"))
        await session.commit()
        yield session
        await session.rollback()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()

@pytest.fixture
async def async_client():
    """Асинхронный HTTP-клиент для тестов."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True
    ) as client:
        yield client

@pytest.fixture(autouse=True)
def mock_redis():
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_client.incr.return_value = 1
    mock_client.expire.return_value = True
    mock_client.setex.return_value = True
    mock_client.ttl.return_value = 900
    mock_pipe = MagicMock()
    mock_pipe.incr.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
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

@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch('app.api.dependencies.check_auth_rate_limit', return_value=None):
        with patch('app.services.rate_limiting_service.RateLimitingService.check_auth_rate_limit', return_value=None):
            yield

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