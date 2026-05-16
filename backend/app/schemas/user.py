"""Pydantic-схемы для управления пользователями."""
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, Literal
from datetime import datetime

class UserResponse(BaseModel):
    """Публичный ответ с данными пользователя (без пароля)."""
    id: int
    login: EmailStr
    role: Literal["worker", "admin"]
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """Схема создания нового пользователя."""
    login: EmailStr = Field(..., min_length=3, max_length=64, examples=["operator@warehouse.dev"])
    password: str = Field(..., min_length=6, max_length=128, examples=["SecurePass123"])
    role: Literal["worker", "admin"] = Field(default="worker")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v


class UserUpdate(BaseModel):
    """Схема обновления пользователя (все поля опциональны)."""
    login: Optional[EmailStr] = Field(None, min_length=3, max_length=64)
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    role: Optional[Literal["worker", "admin"]] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v


class UserListResponse(BaseModel):
    """Ответ со списком пользователей."""
    users: list[UserResponse]
    total: int