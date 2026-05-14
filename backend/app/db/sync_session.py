# app/db/sync_session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import Base, Measurement, User, Product

# Sync engine для Celery-воркеров
sync_engine = create_engine(
    settings.database_url.replace("postgresql+asyncpg://", "postgresql://"),
    pool_pre_ping=True,
    echo=False
)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)

def get_sync_session():
    """Контекстный менеджер для синхронной сессии."""
    return SyncSessionLocal()