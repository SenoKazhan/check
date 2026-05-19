import logging
import sys
from logging.config import dictConfig

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, products, users
from app.api.v1 import measurement, packing, settings, tasks

log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d | session=%(session_id)s user=%(user_id)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "handlers": ["default"],
        "level": "INFO",
    },
    "loggers": {
        "app": {"level": "INFO", "handlers": ["default"], "propagate": False},
    }
}

dictConfig(log_config)


app = FastAPI(title="Warehouse CV", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация маршрутов с группировкой по тегам
app.include_router(auth.router, tags=["Аутентификация"])
app.include_router(products.router, tags=["Справочник товаров"])
app.include_router(measurement.router, prefix="/api/v1", tags=["Измерения"])
app.include_router(packing.router, prefix="/api/v1", tags=["Упаковка"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Задачи"])
app.include_router(settings.router, prefix="/api/v1",
                   tags=["Настройки системы"])
app.include_router(users.router, prefix="/api/v1",
                   tags=["Админ: Пользователи"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
