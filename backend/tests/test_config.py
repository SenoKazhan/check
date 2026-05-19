# tests/test_config.py

from app.core.config import Settings


def test_settings_defaults():
    """Проверка значений по умолчанию."""
    settings = Settings()
    assert settings.jwt_algorithm == "HS256"
    assert settings.bcrypt_cost == 12
    assert settings.min_image_width == 640
    assert settings.min_image_height == 480

def test_allowed_image_types_parsing():
    """Проверка, что allowed_image_types корректно работает как свойство."""
    settings = Settings()
    # По умолчанию должен быть список
    assert isinstance(settings.allowed_image_types, list)
    assert "image/jpeg" in settings.allowed_image_types
    assert "image/png" in settings.allowed_image_types

def test_redis_url_property():
    settings = Settings()
    settings.redis_host = "testhost"
    settings.redis_port = 9999
    assert settings.redis_url == "redis://testhost:9999/0"