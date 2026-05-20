# backend/app/services/rate_limiting_service.py
from app.core.redis import redis_client, AUTH_RATE_LIMIT, AUTH_RATE_WINDOW_SECONDS
from app.domain.exceptions import RateLimitExceededException

class RateLimitingService:
    async def check_auth_rate_limit(self, ip_address: str) -> None:
        key = f"rl:auth:{ip_address}"
        current = await redis_client.get(key)
        
        if current and int(current) >= AUTH_RATE_LIMIT:
            ttl = await redis_client.ttl(key)
            raise RateLimitExceededException(ttl=ttl)
            
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, AUTH_RATE_WINDOW_SECONDS)
        await pipe.execute()