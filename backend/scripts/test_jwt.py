#!/usr/bin/env python3
"""Тестирование JWT: кодирование и декодирование с текущими настройками."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth.manager import AuthManager
from app.core.config import settings

print(f"🔑 Secret key: {settings.jwt_secret_key}")
print(f"🔑 Algorithm: {settings.jwt_algorithm}")

# Создаём тестовый токен
test_payload = {"sub": 1, "role": "admin", "test": True}
token = AuthManager.create_access_token(test_payload)
print(f"🎫 Created token: {token[:50]}...")

# Пытаемся декодировать
decoded = AuthManager.decode_token(token)
print(f"🔓 Decoded: {decoded}")

if decoded and decoded.get("test") is True:
    print("✅ JWT работает корректно!")
else:
    print("❌ Проблема с JWT: проверьте секретный ключ и алгоритм")