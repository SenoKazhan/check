import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Импорт настроек и метаданных
from app.core.config import settings
from app.db.base import Base

# Импорт моделей для autogenerate
from app.db.models.user import User
from app.db.models.product import Product
from app.db.models.measurement import Measurement
from app.db.models.session import PackingSession, PackingItem, PackingResult

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Получает URL из ENV или настроек приложения."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    return settings.database_url


def run_migrations_offline() -> None:
    """Запуск миграций в 'офлайн' режиме (без подключения к БД)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Синхронная функция для выполнения миграций внутри async-контекста."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Запуск миграций в 'онлайн' режиме (с подключением к БД)."""
    connectable = async_engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())