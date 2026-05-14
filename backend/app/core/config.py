"""Конфигурация приложения через pydantic-settings."""
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://app_user:dev_password@postgres:5432/warehouse_db",
        description="URL подключения к PostgreSQL"
    )

    # JWT
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-prod",
        description="Секретный ключ для JWT"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    bcrypt_cost: int = 12

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # CV
    cv_model_ir_path: str = "ir_model/ir_metric_hypersim_vitb"
    cv_model_size: str = "vitb"
    cv_scene_type: str = "indoor"
    cv_multi_scale: bool = True
    cv_max_depth_m: float = 10.0

    # Настройка маркёра
    aruco_marker_size_mm: float = 50.0
    verify_threshold_pct: float = 10.0
    pack_time_limit_sec: int = 30
    pack_n_variants: int = 3

    # Uploads — строковое поле, которое будет преобразовано в список через property
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 10

    allowed_image_types_str: str = Field(
        default="image/jpeg,image/png",
        alias="ALLOWED_IMAGE_TYPES",
        description="Список разрешённых MIME-типов через запятую"
    )

    min_image_width: int = 640
    min_image_height: int = 480

    # CORS — аналогично храним как строку
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
        description="Список разрешённых CORS-источников через запятую"
    )

    @property
    def allowed_image_types(self) -> List[str]:
        """Возвращает список MIME-типов из строки"""
        return [x.strip() for x in self.allowed_image_types_str.split(",") if x.strip()]

    @property
    def cors_origins(self) -> List[str]:
        """Возвращает список CORS-источников из строки"""
        return [x.strip() for x in self.cors_origins_str.split(",") if x.strip()]

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
        populate_by_name=True,
    )


settings = Settings()