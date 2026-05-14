"""
Модуль базы данных: Repository-паттерн для инкапсуляции операций с PostgreSQL.
Все запросы параметризованы, используется asyncpg, логирование через logging.
"""

import logging
from typing import Optional, Dict, Any

import asyncpg

from app.core.config import settings
from app.db.models.user import User

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Repository для работы с базой данных.
    Инкапсулирует все операции чтения/записи, защищает от SQL-инъекций.
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        :param pool: Пул асинхронных соединений asyncpg.
        """
        self.pool = pool

    async def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        """
        Поиск пользователя по логину.
        Возвращает dict с полями пользователя или None.
        """
        row = await self.pool.fetchrow(
            """
            SELECT id, login, password_hash, role, created_at
            FROM users
            WHERE login = $1
            """,
            login,
        )
        return dict(row) if row else None