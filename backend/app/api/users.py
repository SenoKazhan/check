# backend/app/api/users.py

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_permission
from app.auth.manager import AuthManager
from app.db.models.user import User
from app.db.session import get_db
from app.domain.permissions import Permission
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users", 
    tags=["Админ: Пользователи"], 
    dependencies=[Depends(require_permission(Permission.MANAGE_USERS))] 
)


@router.get("/", response_model=UserListResponse, summary="Список пользователей")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    count_query = select(func.count(User.id))
    total = (await db.execute(count_query)).scalar()
    
    return UserListResponse(users=[UserResponse.model_validate(u) for u in users], total=total)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.execute(select(User).where(User.login == payload.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")
    
    new_user = User(
        login=payload.login,
        password_hash=AuthManager.hash_password(payload.password),
        role=payload.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info("Пользователь %s создан администратором %d", new_user.login, current_user.id)
    return UserResponse.model_validate(new_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if payload.role == "worker" and user.role == "admin":
        admins_count = await db.execute(select(func.count(User.id)).where(User.role == "admin"))
        if admins_count.scalar() <= 1:
            raise HTTPException(status_code=400, detail="Нельзя понизить роль последнего администратора")
    
    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = AuthManager.hash_password(update_data.pop("password"))
    
    await db.execute(update(User).where(User.id == user_id).values(**update_data))
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственную учётную запись")
    
    if current_user.role == "admin":
        target = await db.get(User, user_id)
        if target and target.role == "admin":
            admins_count = await db.execute(select(func.count(User.id)).where(User.role == "admin"))
            if admins_count.scalar() <= 1:
                raise HTTPException(status_code=400, detail="Нельзя удалить последнего администратора")
    
    result = await db.execute(delete(User).where(User.id == user_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    await db.commit()
    return None