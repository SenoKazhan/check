# backend/app/core/redis.py
import redis.asyncio as aioredis
from app.core.config import settings

def create_redis_pool() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)

AUTH_RATE_LIMIT = 5
AUTH_RATE_WINDOW_SECONDS = 50