"""Инициализация синхронного Redis-клиента (для rate limiting)."""
import redis
from app.core.config import settings

# Синхронный клиент — вызовы оборачиваем через asyncio.to_thread()
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,
    decode_responses=True,
    socket_connect_timeout=2,
    retry_on_timeout=True,
)

AUTH_RATE_LIMIT = 5
AUTH_RATE_WINDOW = 900  # 15 минут