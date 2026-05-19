# tests/test_auth_manager.py
import pytest
from app.auth.manager import AuthManager
from datetime import timedelta

def test_hash_and_verify_password():
    password = "secret123"
    hashed = AuthManager.hash_password(password)
    assert AuthManager.verify_password(password, hashed)
    assert not AuthManager.verify_password("wrong", hashed)

def test_create_and_decode_token(mock_settings):
    payload = {"sub": "42", "role": "admin"}
    token = AuthManager.create_access_token(payload, expires_delta=timedelta(minutes=5))
    decoded = AuthManager.decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["role"] == "admin"

def test_decode_expired_token(mock_settings):
    # Токен с истекшим сроком (exp в прошлом)
    import time
    from jose import jwt
    expired_payload = {
        "sub": "1",
        "exp": int(time.time()) - 100,
        "iat": int(time.time()) - 200
    }
    token = jwt.encode(expired_payload, mock_settings.jwt_secret_key, algorithm="HS256")
    decoded = AuthManager.decode_token(token)
    assert decoded is None  # должен вернуть None при просрочке

def test_decode_invalid_token():
    result = AuthManager.decode_token("not.a.token")
    assert result is None