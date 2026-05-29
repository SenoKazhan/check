from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    """
    Централизованное управление конфигурацией приложения.
    Соответствует принципу единственной ответственности (SRP) и инверсии зависимостей (DIP).
    """

    # === База данных ===
    database_url: str = Field(
        default="postgresql+asyncpg://app_user:dev_password@postgres:5432/warehouse_db",
        description="URL подключения к PostgreSQL"
    )

    # === JWT ===
    jwt_secret_key: str = Field(default="please-change-me-for-your-safety")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # === Безопасность ===
    bcrypt_cost: int = Field(default=12, ge=4, le=31)

    # === Redis ===
    redis_host: str = "redis"
    redis_port: int = 6379

    # === CV / Depth Anything V2 ===
    cv_model_ir_path: str = "ir_model/ir_metric_hypersim_vitb"
    cv_model_size: str = "vitb"
    cv_enable_alignment: bool = True
    cv_alignment_reference_angle: float = Field(default=0.0, ge=0.0, le=360.0)
    cv_alignment_correction_tolerance: float = Field(default=0.10, ge=0.0, le=0.50)

    # === Верификация ===
    verify_threshold_pct: float = Field(default=10.0, ge=0.0, le=50.0)
    confidence_threshold: float = Field(default=0.4, ge=0.0, le=1.0)

    # === Загрузка файлов ===
    max_upload_size_mb: int = Field(default=10, ge=1, le=100)
    min_image_width: int = Field(default=640, ge=320, le=4096)
    min_image_height: int = Field(default=480, ge=240, le=4096)
    allowed_image_types_str: str = Field(default="image/jpeg,image/png", alias="ALLOWED_IMAGE_TYPES")

    # === Упаковка ===
    pack_time_limit_sec: int = Field(default=30, ge=5, le=300)
    pack_n_variants: int = Field(default=3, ge=1, le=10)
    max_items_per_session: int = Field(default=20, ge=1, le=100)

    # === Инфраструктура ===
    aruco_marker_size_mm: float = 50.0
    upload_dir: str = "/app/uploads"
    cors_origins_str: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # === Seed-данные ===
    first_superuser_email: str = "admin@warehouse.dev"
    first_superuser_password: str = "admin123"

    # === Pydantic v2 конфигурация ===
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True
    )

    # === Валидаторы ===
    @field_validator("allowed_image_types_str", mode="before")
    @classmethod
    def validate_image_types(cls, value: str) -> str:
        if not value:
            return "image/jpeg,image/png"
        return value

    # === Вычисляемые свойства (композиция вместо наследования) ===
    @property
    def allowed_image_types(self) -> List[str]:
        return [
            mime_type.strip().lower()
            for mime_type in self.allowed_image_types_str.split(",")
            if mime_type.strip()
        ]

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origins(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.cors_origins_str.split(",")
            if origin.strip()
        ]


settings = ApplicationSettings()