import asyncio
from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Добавляем корень проекта в PYTHONPATH, чтобы работали импорты из app/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Импортируем настройки и метаданные
from app.core.config import settings
from app.db.base import Base

# 🔧 ВАЖНО: Импорт моделей, чтобы Alembic их "видел" при автогенерации
from app.db.models.user import User
from app.db.models.product import Product
from app.db.models.measurement import Measurement
from app.db.models.session import PackingSession, PackingItem, PackingResult

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config  # <--- ВОТ ЗДЕСЬ создается config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url():
    """Получает URL из ENV или настроек приложения."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    return settings.database_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = async_engine_from_config(
        {"sqlalchemy.url": get_url()}, # Передаем URL напрямую в конфиг движка
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