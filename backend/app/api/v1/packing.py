# backend/app/api/v1/packing.py
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_permission
from app.core.config import settings
from app.db.models.measurement import Measurement
from app.db.models.product import Product
from app.db.models.session import PackingItem, PackingResult, PackingSession
from app.db.models.user import User
from app.db.session import get_db
from app.domain.exceptions import AccessDeniedException
from app.domain.permissions import Permission
from app.packing.solver import BinPackingSolver
from app.packing.validator import validate_stability
from app.schemas.packing import Item as PackingItemSchema

router = APIRouter(prefix="/packing", tags=["Packing"])


class PackingRequestItem(BaseModel):
    product_id: int
    quantity: int = 1


class DirectPackingRequest(BaseModel):
    items: list[PackingRequestItem]
    enable_stability: bool = True  # Включить stability constraints


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


@router.post("/sessions/{session_id}/solve")
async def solve_session(
    session_id: int,
    enable_stability: bool = Query(default=True, description="Включить stability constraints"),
    user: User = Depends(require_permission(Permission.EXECUTE_PACKING)),
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(PackingSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Сессия не найдена")

    query = select(PackingItem, Measurement).join(
        Measurement, PackingItem.measurement_id == Measurement.id
    ).where(PackingItem.session_id == session_id)
    items_data = (await db.execute(query)).all()

    if not items_data:
        raise HTTPException(400, "Сессия пуста")

    packing_items = []
    for pi, m in items_data:
        if not m.length_mm or not m.width_mm or not m.height_mm:
            raise HTTPException(
                status_code=400,
                detail=f"Измерение ID={m.id} не имеет корректных габаритов"
            )
        packing_items.append(
            PackingItemSchema(
                product_id=m.product_id or 0,
                length_mm=m.length_mm, width_mm=m.width_mm, height_mm=m.height_mm,
                quantity=pi.quantity
            )
        )

    solver = BinPackingSolver(
        time_limit_sec=settings.pack_time_limit_sec,
        n_variants=settings.pack_n_variants,
        enable_stability=enable_stability
    )
    solutions = solver.solve(packing_items)

    if not solutions:
        session.status = "error"
        await db.commit()
        raise HTTPException(500, "Решение не найдено")

    await db.execute(delete(PackingResult).where(PackingResult.session_id == session_id))

    for idx, sol in enumerate(solutions):
        box_l, box_w, box_h = sol["box"]

        placements_json = json.dumps([{
            "item_id": p["product_id"],
            "x_mm": p["x"],
            "y_mm": p["y"],
            "z_mm": p["z"],
            "length_mm": p["length"],
            "width_mm": p["width"],
            "height_mm": p["height"],
            "rotated": p.get("rotation", False)
        } for p in sol["placements"]], ensure_ascii=False)

        result = PackingResult(
            session_id=session_id, variant_index=idx,
            box_l_mm=box_l, box_w_mm=box_w, box_h_mm=box_h,
            box_volume_cm3=sol["volume"], placements_json=placements_json,
            selected=(idx == 0)
        )
        db.add(result)

    session.status = "done"
    await db.commit()
    return {"status": "success", "variants": len(solutions)}


@router.get("/sessions/{session_id}/results")
async def get_results(
    session_id: int,
    user: User = Depends(require_permission(Permission.EXECUTE_PACKING)),
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(PackingSession, session_id)
    if not session or session.user_id != user.id:
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
async def select_result(
    session_id: int,
    result_id: int,
    user: User = Depends(require_permission(Permission.EXECUTE_PACKING)),
    db: AsyncSession = Depends(get_db)
):
    session = await db.get(PackingSession, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Сессия не найдена")

    await db.execute(update(PackingResult).where(
        PackingResult.session_id == session_id
    ).values(selected=False))
    await db.execute(update(PackingResult).where(
        PackingResult.id == result_id
    ).values(selected=True))
    await db.commit()
    return {"status": "ok"}


@router.post("/solve-direct")
async def solve_direct(
    request_body: DirectPackingRequest,
    user: User = Depends(require_permission(Permission.EXECUTE_PACKING)),
    db: AsyncSession = Depends(get_db)
):
    packing_items = []

    for req_item in request_body.items:
        product = await db.get(Product, req_item.product_id)
        if not product:
            raise HTTPException(404, detail=f"Товар с ID {req_item.product_id} не найден")

        if not product.ref_length_mm or not product.ref_width_mm or not product.ref_height_mm:
            raise HTTPException(
                status_code=400,
                detail=f"У товара '{product.name}' отсутствуют эталонные габариты"
            )

        packing_items.append(
            PackingItemSchema(
                product_id=product.id,
                length_mm=product.ref_length_mm,
                width_mm=product.ref_width_mm,
                height_mm=product.ref_height_mm,
                quantity=req_item.quantity
            )
        )

    if not packing_items:
        raise HTTPException(400, "Список товаров пуст")

    solver = BinPackingSolver(
        time_limit_sec=settings.pack_time_limit_sec,
        n_variants=settings.pack_n_variants,
        enable_stability=request_body.enable_stability
    )
    solutions = solver.solve(packing_items)

    if not solutions:
        raise HTTPException(500, "Решение не найдено")

    formatted_results = []
    for idx, sol in enumerate(solutions):
        box_l, box_w, box_h = sol["box"]

        placements_json = [{
            "item_id": p["product_id"],
            "x_mm": p["x"],
            "y_mm": p["y"],
            "z_mm": p["z"],
            "length_mm": p["length"],
            "width_mm": p["width"],
            "height_mm": p["height"],
            "rotated": p.get("rotation", False)
        } for p in sol["placements"]]

        # Проверяем стабильность
        stability_report = validate_stability(sol["placements"])

        formatted_results.append({
            "variant_index": idx,
            "box_l_mm": box_l,
            "box_w_mm": box_w,
            "box_h_mm": box_h,
            "box_volume_cm3": sol["volume"],
            "placements": placements_json,
            "selected": (idx == 0),
            "stability_enabled": sol.get("stability_enabled", False),
            "stability_report": stability_report,
        })

    return formatted_results