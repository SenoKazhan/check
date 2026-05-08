import asyncio
import logging
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.manager import AuthManager
from app.core.redis import redis_client, AUTH_RATE_LIMIT, AUTH_RATE_WINDOW
from app.db.models.user import User
from app.db.session import get_db

logger = logging.getLogger(__name__)


async def check_auth_rate_limit(request: Request) -> None:
    try:
        ip = request.client.host
        key = f"rl:auth:{ip}"
        current = await asyncio.to_thread(redis_client.get, key)
        
        if current and int(current) >= AUTH_RATE_LIMIT:
            ttl = await asyncio.to_thread(redis_client.ttl, key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Превышено количество попыток входа. Повторите через {ttl} сек."
            )
        
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, AUTH_RATE_WINDOW)
        await asyncio.to_thread(pipe.execute)
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Отсутствует токен")

    payload = AuthManager.decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Невалидный токен")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def require_role(required_role: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав"
            )
        return current_user
    return role_checker