"""Конфигурация приложения через pydantic-settings."""
from pathlib import Path
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://app_user:dev_password@localhost:5432/warehouse_db"

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    bcrypt_cost: int = 12

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # CV & Packing
    # Избегаем префикса model_, так как Pydantic его резервирует
    cv_model_ir_path: str = "ir_model/ir_metric_hypersim_vitb"
    cv_model_size: str = "vitb"
    cv_scene_type: str = "indoor"
    cv_multi_scale: bool = True
    cv_max_depth_m: float = 10.0

    aruco_marker_size_mm: float = 50.0
    verify_threshold_pct: float = 10.0
    pack_time_limit_sec: int = 30
    pack_n_variants: int = 3

    # Uploads
    max_upload_size_mb: int = 10
    # Убрали List[str], Pydantic сам спарсит строку, если есть валидатор ниже
    allowed_image_types: List[str] = ["image/jpeg", "image/png"]
    min_image_width: int = 640
    min_image_height: int = 480

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("allowed_image_types", mode="before")
    @classmethod
    def parse_image_types(cls, v):
        """Превращает строку 'image/jpeg,image/png' из .env в список"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return v
        return ["image/jpeg", "image/png"]  # fallback

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # Игнорируем конфликт префикса model_
        protected_namespaces=("settings_",)
    )


settings = Settings()
