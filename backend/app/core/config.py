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
        default="please-change-me-for-your-safety ",
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

    # ─────────────────────────────────────────────────────────────────────────────
    # Динамические настройки (могут изменяться через UI)
    # ─────────────────────────────────────────────────────────────────────────────

    # Компьютерное зрение — выравнивание
    cv_enable_alignment: bool = Field(
        default=True,
        description="Включить выравнивание объектов относительно сетки"
    )
    cv_alignment_reference_angle: float = Field(
        default=0.0,
        ge=0, le=360,
        description="Эталонный угол оси разметки площадки (градусы)"
    )
    cv_alignment_correction_tolerance: float = Field(
        default=0.10,
        ge=0.0, le=0.50,
        description="Допуск коррекции масштаба при выравнивании (±10–50%)"
    )

    # Верификация измерений
    verify_threshold_pct: float = Field(
        default=10.0,
        ge=0, le=50,
        description="Порог отклонения измерений от эталона (%)"
    )
    confidence_threshold: float = Field(
        default=0.4,
        ge=0.0, le=1.0,
        description="Минимальная уверенность модели для автоматического подтверждения"
    )

    # Загрузка изображений
    max_upload_size_mb: int = Field(
        default=10,
        ge=1, le=100,
        description="Максимальный размер файла загрузки (МБ)"
    )
    min_image_width: int = Field(
        default=640,
        ge=320, le=4096,
        description="Минимальная ширина изображения (пиксели)"
    )
    min_image_height: int = Field(
        default=480,
        ge=240, le=4096,
        description="Минимальная высота изображения (пиксели)"
    )

    # Упаковка
    pack_time_limit_sec: int = Field(
        default=30,
        ge=5, le=300,
        description="Лимит времени решателя упаковки (секунды)"
    )
    pack_n_variants: int = Field(
        default=3,
        ge=1, le=10,
        description="Количество вариантов упаковки для генерации"
    )
    max_items_per_session: int = Field(
        default=20,
        ge=1, le=100,
        description="Максимальное количество товаров в сеансе упаковки"
    )

    # ─────────────────────────────────────────────────────────────────────────────
    # Методы для работы с динамическими настройками
    # ─────────────────────────────────────────────────────────────────────────────

    def get_dynamic_settings_keys(self) -> list[str]:
        """Возвращает список полей, доступных для изменения через UI."""
        return [
            "cv_enable_alignment",
            "cv_alignment_reference_angle",
            "cv_alignment_correction_tolerance",
            "verify_threshold_pct",
            "confidence_threshold",
            "max_upload_size_mb",
            "min_image_width",
            "min_image_height",
            "pack_time_limit_sec",
            "pack_n_variants",
            "max_items_per_session",
        ]

    def get_settings_metadata(self) -> dict[str, dict]:
        """Метаданные настроек для генерации формы в UI."""
        return {
            "cv_enable_alignment": {
                "label": "Выравнивание объектов",
                "type": "boolean",
                "group": "computer_vision",
                "description": "Автоматически выравнивать объекты относительно сетки площадки",
            },
            "cv_alignment_reference_angle": {
                "label": "Эталонный угол",
                "type": "number",
                "unit": "°",
                "step": 1,
                "group": "computer_vision",
                "description": "Угол оси разметки для выравнивания",
            },
            "cv_alignment_correction_tolerance": {
                "label": "Допуск коррекции",
                "type": "number",
                "unit": "%",
                "step": 0.01,
                "multiplier": 100,
                "group": "computer_vision",
                "description": "Максимальное отклонение при коррекции масштаба",
            },
            "verify_threshold_pct": {
                "label": "Порог верификации",
                "type": "number",
                "unit": "%",
                "step": 0.5,
                "group": "verification",
                "description": "Допустимое отклонение от эталонных габаритов",
            },
            "confidence_threshold": {
                "label": "Порог уверенности",
                "type": "number",
                "unit": "",
                "step": 0.05,
                "group": "verification",
                "description": "Минимальная уверенность модели для авто-подтверждения",
            },
            "max_upload_size_mb": {
                "label": "Макс. размер файла",
                "type": "number",
                "unit": "МБ",
                "step": 1,
                "group": "uploads",
                "description": "Ограничение размера загружаемых изображений",
            },
            "min_image_width": {
                "label": "Мин. ширина",
                "type": "number",
                "unit": "px",
                "step": 10,
                "group": "uploads",
                "description": "Минимальная допустимая ширина изображения",
            },
            "min_image_height": {
                "label": "Мин. высота",
                "type": "number",
                "unit": "px",
                "step": 10,
                "group": "uploads",
                "description": "Минимальная допустимая высота изображения",
            },
            "pack_time_limit_sec": {
                "label": "Лимит времени упаковки",
                "type": "number",
                "unit": "сек",
                "step": 5,
                "group": "packing",
                "description": "Максимальное время работы решателя упаковки",
            },
            "pack_n_variants": {
                "label": "Количество вариантов",
                "type": "number",
                "unit": "шт",
                "step": 1,
                "group": "packing",
                "description": "Сколько вариантов упаковки генерировать",
            },
            "max_items_per_session": {
                "label": "Макс. товаров в сеансе",
                "type": "number",
                "unit": "шт",
                "step": 1,
                "group": "packing",
                "description": "Ограничение количества товаров в одной сессии",
            },
        }

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
