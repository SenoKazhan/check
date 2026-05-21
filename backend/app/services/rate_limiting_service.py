# backend/app/services/rate_limiting_service.py
import redis.asyncio as aioredis
from app.core.redis import AUTH_RATE_LIMIT, AUTH_RATE_WINDOW_SECONDS
from app.domain.exceptions import RateLimitExceededException

class RateLimitingService:
    def __init__(self, redis_client: aioredis.Redis):
        self._redis_client = redis_client

    async def check_auth_rate_limit(self, ip_address: str) -> None:
        key = f"rl:auth:{ip_address}"
        current = await self._redis_client.get(key)
        
        if current and int(current) >= AUTH_RATE_LIMIT:
            ttl = await self._redis_client.ttl(key)
            raise RateLimitExceededException(ttl=ttl)
            
        pipe = self._redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, AUTH_RATE_WINDOW_SECONDS)
        await pipe.execute()