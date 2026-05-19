import pytest
from app.auth.manager import AuthManager

def test_password_hashing_and_verification():
    """Тест: хэширование и проверка пароля работают корректно."""
    plain_password = "secure_password_123"
    hashed = AuthManager.hash_password(plain_password)
    
    # Хэш не должен быть равен паролю
    assert hashed != plain_password
    # Верификация правильного пароля проходит
    assert AuthManager.verify_password(plain_password, hashed) is True
    # Верификация неправильного пароля не проходит
    assert AuthManager.verify_password("wrong_password", hashed) is False

def test_create_and_decode_token():
    """Тест: создание и декодирование JWT-токена."""
    data = {"sub": "1", "role": "admin"}
    token = AuthManager.create_access_token(data=data)
    
    # Токен должен быть строкой
    assert isinstance(token, str)
    
    # Декодирование должно вернуть те же данные
    payload = AuthManager.decode_token(token)
    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["role"] == "admin"