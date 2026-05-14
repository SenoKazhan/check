# backend/migrations/env.py
import sys
from pathlib import Path

# Гарантируем, что корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import async_engine_from_config
import asyncio
import os

# Импорт настроек ПОСЛЕ добавления пути
from app.core.config import settings  # ← Ваш конфиг с pydantic-settings
from app.db.base import Base

target_metadata = Base.metadata

config = context.config

# ПРИОРИТЕТ: явно переписываем URL из настроек приложения
# Это гарантированно использует сервисное имя 'postgres' из docker-compose
if hasattr(settings, 'database_url') and settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)
elif os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))



def process_revision_directives(context, revision, directives):
    if directives[0].rev_id is None:
        import uuid
        directives[0].rev_id = uuid.uuid4().hex

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
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
