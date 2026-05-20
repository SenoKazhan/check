# backend/app/main.py
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.redis import create_redis_pool, redis_client
from app.domain.exceptions import DomainException, AccessDeniedException, RateLimitExceededException
from app.api import auth
from app.api.v1 import measurement, packing

logger = logging.getLogger(__name__)

app = FastAPI(title="Warehouse CV", version="0.1.0")

@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_client = await create_redis_pool()

@app.on_event("shutdown")
async def shutdown_event():
    global redis_client
    if redis_client:
        await redis_client.close()

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

app.include_router(auth.router, tags=["Authentication"])
app.include_router(measurement.router, prefix="/api/v1", tags=["Measurements"])
app.include_router(packing.router, prefix="/api/v1", tags=["Packing"])

@app.get("/health")
def health_check():
    return {"status": "ok"}