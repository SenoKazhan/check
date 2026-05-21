# backend/app/api/products.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_permission
from app.db.models.product import Product
from app.db.models.user import User
from app.db.session import get_db
from app.domain.permissions import Permission
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

def format_product(p: Product) -> dict:
    """Преобразует модель БД в формат, ожидаемый фронтендом и солвером."""
    return {
        "id": p.id,
        "name": p.name,
        "qr_code": p.qr_code,
        "length_mm": p.ref_length_mm or 0.0, # Маппинг ref_ -> обычным
        "width_mm": p.ref_width_mm or 0.0,
        "height_mm": p.ref_height_mm or 0.0,
        "notes": p.notes
    }

@router.get("/")
async def list_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).order_by(Product.id))
    products = result.scalars().all()
    return [format_product(p) for p in products]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_PRODUCTS))
):
    if payload.qr_code:
        existing = await db.execute(
            select(Product).where(Product.qr_code == payload.qr_code)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Товар с QR-кодом '{payload.qr_code}' уже существует"
            )
    
    db_product = Product(
        name=payload.name,
        qr_code=payload.qr_code,
        ref_length_mm=payload.ref_length_mm, 
        ref_width_mm=payload.ref_width_mm,    
        ref_height_mm=payload.ref_height_mm,  
        notes=payload.notes
    )
    db.add(db_product)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Товар с таким уникальным идентификатором уже существует"
        )
    await db.refresh(db_product)
    return format_product(db_product)

@router.get("/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return format_product(product)


@router.put("/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_PRODUCTS))
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if payload.name is not None: product.name = payload.name
    if payload.qr_code is not None: product.qr_code = payload.qr_code
    if payload.ref_length_mm is not None: product.ref_length_mm = payload.ref_length_mm
    if payload.ref_width_mm is not None: product.ref_width_mm = payload.ref_width_mm
    if payload.ref_height_mm is not None: product.ref_height_mm = payload.ref_height_mm
    if payload.notes is not None: product.notes = payload.notes
    
    await db.commit()
    await db.refresh(product)
    return format_product(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_PRODUCTS))
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    await db.delete(product)
    await db.commit()