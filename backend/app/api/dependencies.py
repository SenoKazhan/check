# backend/app/api/dependencies.py
from functools import wraps
from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository
from app.services.authentication_service import AuthenticationService
from app.services.rate_limiting_service import RateLimitingService
from app.core.config import ApplicationSettings, settings
from app.domain.permissions import Permission, ROLE_PERMISSIONS
from app.domain.exceptions import RateLimitExceededException, DomainException

def get_authentication_service() -> AuthenticationService:
    return AuthenticationService(settings)

def get_rate_limiting_service() -> RateLimitingService:
    return RateLimitingService()

def get_user_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)

async def get_current_user(
    request: Request,
    auth_service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)]
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = auth_service.decode_token(token)
        user_id = int(payload.get("sub"))
    except (DomainException, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def check_auth_rate_limit(
    request: Request,
    rate_service: Annotated[RateLimitingService, Depends(get_rate_limiting_service)]
) -> None:
    try:
        await rate_service.check_auth_rate_limit(request.client.host)
    except RateLimitExceededException as e:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded. Retry in {e.ttl} sec.")

def require_permission(permission: Permission):
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = ROLE_PERMISSIONS.get(current_user.role, [])
        if permission not in user_permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return permission_checker