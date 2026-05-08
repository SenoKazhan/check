import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import check_auth_rate_limit, get_current_user
from app.auth.manager import AuthManager
from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserResponse)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_auth_rate_limit)
):
    result = await db.execute(select(User).where(User.login == payload.login))
    user = result.scalar_one_or_none()

    if not user or not AuthManager.verify_password(payload.password, user.password_hash):
        logger.warning(f"Failed login for '{payload.login}' from {request.client.host}")
        raise HTTPException(status_code=401, detail="Неверные учётные данные")

    access_token = AuthManager.create_access_token(
        data={"sub": user.id, "role": user.role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/"
    )

    logger.info(f"User '{user.login}' logged in from {request.client.host}")
    return UserResponse(id=user.id, login=user.login, role=user.role)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(id=current_user.id, login=current_user.login, role=current_user.role)