from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.packing.solver import BinPackingSolver
from app.core.config import settings
import json

router = APIRouter(prefix="/packing", tags=["Упаковка"])

@router.post("/sessions")
async def create_session(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.db.models.session import PackingSession
    session = PackingSession(user_id=user.id, status="pending")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"session_id": session.id, "status": "pending"}

@router.post("/sessions/{session_id}/items")
async def add_item(session_id: int, measurement_id: int, quantity: int = 1,
                   user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.db.models.session import PackingSession, PackingItem
    from app.db.models.measurement import Measurement
    
    sess = await db.get(PackingSession, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(404, "Сессия не найдена")
    if sess.status != "pending":
        raise HTTPException(400, f"Статус сессии: {sess.status}")
        
    meas = await db.get(Measurement, measurement_id)
    if not meas:
        raise HTTPException(404, "Измерение не найдено")
    
    item = PackingItem(session_id=session_id, measurement_id=measurement_id, quantity=quantity)
    db.add(item)
    await db.commit()
    return {"status": "ok", "item_id": item.id}

@router.post("/sessions/{session_id}/solve")
async def solve_session(session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.db.models.session import PackingSession, PackingItem, PackingResult
    from app.db.models.measurement import Measurement
    from app.schemas.packing import Item as PackingItemSchema
    
    sess = await db.get(PackingSession, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(404, "Сессия не найдена")
    
    # Собираем товары
    query = select(PackingItem, Measurement).join(
        Measurement, PackingItem.measurement_id == Measurement.id
    ).where(PackingItem.session_id == session_id)
    items_data = (await db.execute(query)).all()
    
    if not items_data:
        raise HTTPException(400, "Сессия пуста")
    
    packing_items = [
        PackingItemSchema(
            product_id=m.product_id or 0,
            length_mm=m.length_mm, width_mm=m.width_mm, height_mm=m.height_mm,
            quantity=pi.quantity
        ) for pi, m in items_data
    ]
    
    # Запускаем solver
    solver = BinPackingSolver(
        time_limit_sec=settings.pack_time_limit_sec,
        n_variants=settings.pack_n_variants
    )
    solutions = solver.solve(packing_items)
    
    if not solutions:
        sess.status = "error"
        await db.commit()
        raise HTTPException(500, "Решение не найдено")
    
    # Сохраняем результаты
    for idx, sol in enumerate(solutions):
        placements_json = json.dumps([{
            "item_id": p["product_id"], "x_mm": p["x"], "y_mm": p["y"], 
            "z_mm": p["z"], "rotated": p.get("rotation", False)
        } for p in sol["placements"]], ensure_ascii=False)
        
        result = PackingResult(
            session_id=session_id, variant_index=idx,
            box_l_mm=sol["box"][0], box_w_mm=sol["box"][1], box_h_mm=sol["box"][2],
            box_volume_cm3=sol["volume"], placements_json=placements_json,
            selected=(idx == 0)
        )
        db.add(result)
    
    sess.status = "done"
    await db.commit()
    return {"status": "success", "variants": len(solutions)}

@router.get("/sessions/{session_id}/results")
async def get_results(session_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.db.models.session import PackingSession, PackingResult
    sess = await db.get(PackingSession, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(404, "Сессия не найдена")
    
    results = await db.execute(
        select(PackingResult).where(
            PackingResult.session_id == session_id
        ).order_by(PackingResult.variant_index)
    )
    return [{
        "variant_index": r.variant_index, "box_l_mm": r.box_l_mm,
        "box_w_mm": r.box_w_mm, "box_h_mm": r.box_h_mm,
        "box_volume_cm3": r.box_volume_cm3,
        "placements": json.loads(r.placements_json),
        "selected": r.selected
    } for r in results.scalars().all()]

@router.post("/sessions/{session_id}/select/{result_id}")
async def select_result(session_id: int, result_id: int, 
                       user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    

    from app.db.models.session import PackingResult, PackingSession
    
    sess = await db.get(PackingSession, session_id)
    if not sess or sess.user_id != user.id:
        raise HTTPException(404, "Сессия не найдена")
    
    # Сбрасываем все, помечаем выбранный
    await db.execute(update(PackingResult).where(
        PackingResult.session_id == session_id
    ).values(selected=False))
    await db.execute(update(PackingResult).where(
        PackingResult.id == result_id
    ).values(selected=True))
    await db.commit()
    return {"status": "ok"}