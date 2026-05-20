# backend/app/api/v1/packing.py
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_permission
from app.db.models.user import User
from app.db.models.session import PackingSession, PackingItem, PackingResult
from app.db.models.measurement import Measurement
from app.db.session import get_db
from app.packing.solver import BinPackingSolver
from app.schemas.packing import Item as PackingItemSchema
from app.core.config import settings
from app.domain.permissions import Permission
from app.domain.exceptions import AccessDeniedException

router = APIRouter(prefix="/packing", tags=["Packing"])

def verify_session_ownership(session: PackingSession, user: User):
    if session.user_id != user.id:
        raise AccessDeniedException("You do not own this session")

@router.post("/sessions")
async def create_session(
    user: User = Depends(require_permission(Permission.EXECUTE_PACKING)),
    db: AsyncSession = Depends(get_db)
):
    session = PackingSession(user_id=user.id, status="pending")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "status": "pending"}

@router.post("/sessions/{session_id}/items")
async def add_item(
    session_id: int,
    measurement_id: int,
    quantity: int = 1,
    user: User = Depends(require_permission(Permission.EXECUTE_PACKING)),
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(PackingSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    verify_session_ownership(session, user)

    if session.status != "pending":
        raise HTTPException(400, f"Session status is {session.status}")
        
    measurement = await db.get(Measurement, measurement_id)
    if not measurement:
        raise HTTPException(404, "Measurement not found")
    
    item = PackingItem(session_id=session_id, measurement_id=measurement_id, quantity=quantity)
    db.add(item)
    await db.commit()
    return {"status": "ok", "item_id": item.id}