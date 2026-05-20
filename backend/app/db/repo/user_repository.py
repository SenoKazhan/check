# backend/app/db/repo/user_repository.py
"""
Repository-паттерн для работы с таблицей пользователей.
Интегрируется в систему DI FastAPI через AsyncSession.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User

class UserRepository:
    """Инкапсулирует запросы к таблице users."""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Получает пользователя по первичному ключу."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()