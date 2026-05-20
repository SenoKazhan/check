"""
Модульные тесты для AuthManager.
"""
import pytest
from datetime import timedelta
from jose import jwt, JWTError

from app.auth.manager import AuthManager
from app.core.config import settings


class TestAuthManager:
    """Тесты класса AuthManager."""

    def test_hash_and_verify_password(self):
        """Проверка хэширования и верификации пароля."""
        password = "SecureP@ssw0rd!"
        hashed = AuthManager.hash_password(password)
        
        # Верный пароль должен проходить
        assert AuthManager.verify_password(password, hashed) is True
        
        # Неверный пароль должен отклоняться
        assert AuthManager.verify_password("wrong_password", hashed) is False
        
        # Хэш должен отличаться при каждом вызове (из-за соли)
        hashed2 = AuthManager.hash_password(password)
        assert hashed != hashed2

    def test_create_access_token(self, mock_settings):
        """Проверка создания JWT-токена."""
        payload = {"sub": "42", "role": "admin", "extra": "data"}
        token = AuthManager.create_access_token(
            payload, 
            expires_delta=timedelta(minutes=5)
        )
        
        assert isinstance(token, str)
        assert len(token.split('.')) == 3  # JWT имеет 3 части

    def test_decode_valid_token(self, mock_settings):
        """Декодирование валидного токена."""
        payload = {"sub": "123", "role": "worker", "test": True}
        token = AuthManager.create_access_token(payload)
        
        decoded = AuthManager.decode_token(token)
        
        assert decoded is not None
        assert decoded["sub"] == "123"
        assert decoded["role"] == "worker"
        assert decoded["test"] is True

    def test_decode_expired_token(self, mock_settings):
        """Токен с истёкшим сроком должен возвращать None."""
        import time
        expired_payload = {
            "sub": "1",
            "exp": int(time.time()) - 100,  # Истёк 100 секунд назад
            "iat": int(time.time()) - 200
        }
        token = jwt.encode(
            expired_payload, 
            mock_settings.jwt_secret_key, 
            algorithm="HS256"
        )
        
        decoded = AuthManager.decode_token(token)
        assert decoded is None

    def test_decode_invalid_token(self):
        """Невалидный токен должен возвращать None."""
        result = AuthManager.decode_token("not.a.valid.token")
        assert result is None
        
        result = AuthManager.decode_token("")
        assert result is None

    def test_decode_wrong_algorithm(self, mock_settings):
        """Токен, подписанный другим алгоритмом, должен отклоняться."""
        payload = {"sub": "1", "exp": 9999999999}
        # Подписываем другим ключом
        token = jwt.encode(payload, "wrong_secret_key", algorithm="HS256")
        
        decoded = AuthManager.decode_token(token)
        assert decoded is None