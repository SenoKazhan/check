from sqlalchemy import String, DateTime, func, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, server_default="worker")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    measurements = relationship(
        "Measurement", 
        back_populates="user", 
        lazy="select"
    )
    sessions = relationship(
        "PackingSession", 
        back_populates="user", 
        lazy="select"
    )
    
    __table_args__ = (
        CheckConstraint("role IN ('worker', 'admin')", name="check_role_values"),
    )