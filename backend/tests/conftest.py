# tests/conftest.py
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_settings():
    """Мок настроек для тестов, не требующих БД."""
    with patch('app.core.config.settings') as mock:
        mock.jwt_secret_key = "test-secret-key"
        mock.jwt_algorithm = "HS256"
        mock.access_token_expire_minutes = 30
        mock.bcrypt_cost = 12
        yield mock