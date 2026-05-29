# backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import auth, products, users
from app.api.v1 import measurement, packing, qr
from app.core.redis import create_redis_pool
from app.db.session import async_session_factory
from app.domain.exceptions import (
    AccessDeniedException,
    DomainException,
    RateLimitExceededException,
)

logger = logging.getLogger(__name__)

INITIAL_PRODUCTS = [
    {"name": "Смартфон стандарт", "ref_length_mm": 160, "ref_width_mm": 75, "ref_height_mm": 8},
    {"name": "Планшет 10 дюймов", "ref_length_mm": 245, "ref_width_mm": 170, "ref_height_mm": 7},
    {"name": "Ноутбук 15 дюймов", "ref_length_mm": 360, "ref_width_mm": 250, "ref_height_mm": 20},
    {"name": "Наушники накладные", "ref_length_mm": 200, "ref_width_mm": 180, "ref_height_mm": 80},
    {"name": "Клавиатура механическая", "ref_length_mm": 440, "ref_width_mm": 140, "ref_height_mm": 35},
    {"name": "Мышь компьютерная", "ref_length_mm": 120, "ref_width_mm": 70, "ref_height_mm": 40},
    {"name": "Книга крупная", "ref_length_mm": 250, "ref_width_mm": 200, "ref_height_mm": 30},
    {"name": "Кружка керамическая", "ref_length_mm": 120, "ref_width_mm": 90, "ref_height_mm": 100},
    {"name": "Тарелка обеденная", "ref_length_mm": 270, "ref_width_mm": 270, "ref_height_mm": 25},
    {"name": "Кастрюля 3 литра", "ref_length_mm": 250, "ref_width_mm": 200, "ref_height_mm": 150},
    {"name": "Обувь кроссовки (пара)", "ref_length_mm": 320, "ref_width_mm": 210, "ref_height_mm": 120},
    {"name": "Футболка сложенная", "ref_length_mm": 250, "ref_width_mm": 200, "ref_height_mm": 30},
    {"name": "Куртка сложенная", "ref_length_mm": 400, "ref_width_mm": 300, "ref_height_mm": 80},
    {"name": "Рюкзак городской", "ref_length_mm": 450, "ref_width_mm": 300, "ref_height_mm": 150},
    {"name": "Чемодан средний", "ref_length_mm": 650, "ref_width_mm": 450, "ref_height_mm": 250},
    {"name": "Коробка конфет", "ref_length_mm": 250, "ref_width_mm": 200, "ref_height_mm": 60},
    {"name": "Бутылка вина", "ref_length_mm": 80, "ref_width_mm": 80, "ref_height_mm": 320},
    {"name": "Банка кофе", "ref_length_mm": 100, "ref_width_mm": 100, "ref_height_mm": 200},
    {"name": "Тостер", "ref_length_mm": 300, "ref_width_mm": 180, "ref_height_mm": 200},
    {"name": "Миксер кухонный", "ref_length_mm": 220, "ref_width_mm": 160, "ref_height_mm": 310},
]

@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.redis_client = create_redis_pool()
    
    async with async_session_factory() as db:
        try:
            result = await db.execute(text("SELECT id FROM products LIMIT 1"))
            if result.first() is None:
                logger.info("Таблица товаров пуста. Заполняю начальными данными...")
                for p_data in INITIAL_PRODUCTS:
                    await db.execute(
                        text("""
                            INSERT INTO products (name, ref_length_mm, ref_width_mm, ref_height_mm) 
                            VALUES (:name, :ref_length_mm, :ref_width_mm, :ref_height_mm)
                        """),
                        p_data
                    )
                await db.commit()
                logger.info("Успешно добавлено %d товаров.", len(INITIAL_PRODUCTS))
        except Exception as e:
            logger.warning(f"Seeding пропущен (таблица не готова?): {e}")
            await db.rollback()
        
    yield
    
    if application.state.redis_client:
        await application.state.redis_client.close()

app = FastAPI(title="Warehouse CV", version="0.1.0", lifespan=lifespan)

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    status_code = 400
    if isinstance(exc, AccessDeniedException):
        status_code = 403
    elif isinstance(exc, RateLimitExceededException):
        status_code = 429
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(qr.router, prefix="/api/v1", tags=["QR Scanner"])
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(products.router, prefix="/api/v1", tags=["Products"])
app.include_router(measurement.router, prefix="/api/v1", tags=["Measurements"])
app.include_router(packing.router, prefix="/api/v1", tags=["Packing"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])

@app.get("/health")
def health_check():
    return {"status": "ok"}