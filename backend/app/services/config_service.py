"""
Сервис для получения актуальных настроек с учётом динамических переопределений.
"""
import logging
from typing import Any
from functools import lru_cache

from app.core.config import settings
from app.db.repo.settings_repo import SettingsRepository

logger = logging.getLogger(__name__)


class ConfigService:
    """
    Предоставляет единый интерфейс для получения настроек.
    Приоритет: динамическое значение из БД > дефолт из config > fallback.
    """

    def __init__(self, settings_repo: SettingsRepository):
        self.settings_repo = settings_repo
        self._cache: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        """
        Получает значение настройки с кэшированием.
        
        :param key: Имя настройки (должно быть в settings.get_dynamic_settings_keys())
        :return: Значение в нативном типе или дефолт из config
        """
        # Проверяем кэш
        if key in self._cache:
            return self._cache[key]

        # Проверяем БД
        db_setting = await self.settings_repo.get_setting(key)
        if db_setting and db_setting.get_typed_value() is not None:
            value = db_setting.get_typed_value()
            logger.debug("Настройка '%s' = %s (из БД)", key, value)
            self._cache[key] = value
            return value

        # Фоллбэк на дефолт из config
        if hasattr(settings, key):
            value = getattr(settings, key)
            logger.debug("Настройка '%s' = %s (default из config)", key, value)
            self._cache[key] = value
            return value

        logger.warning("Неизвестная настройка: '%s'", key)
        return None

    async def get_all_active(self) -> dict[str, Any]:
        """Получает все активные настройки как словарь."""
        result = {}
        for key in settings.get_dynamic_settings_keys():
            result[key] = await self.get(key)
        return result

    def invalidate_cache(self, key: str | None = None) -> None:
        """Очищает кэш (полностью или для конкретного ключа)."""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()