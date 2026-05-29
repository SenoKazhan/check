"""
API для управления системными настройками.
Доступно только для роли 'admin'.
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user, require_permission
from app.domain.permissions import Permission
from app.core.config import settings
from app.db.session import get_db
from app.db.models.user import User
from app.db.repo.settings_repo import SettingsRepository
from app.services.config_service import ConfigService
from app.schemas.settings import (
    SettingResponse,
    SettingUpdateRequest,
    SettingsGroupResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Настройки"])


def get_settings_repo(db: AsyncSession = Depends(get_db)) -> SettingsRepository:
    """Factory для SettingsRepository."""
    return SettingsRepository(db)


def get_config_service(
    repo: Annotated[SettingsRepository, Depends(get_settings_repo)],
) -> ConfigService:
    """Factory для ConfigService."""
    return ConfigService(repo)


@router.get("/", response_model=SettingsGroupResponse)
async def list_settings(
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_SETTINGS))],
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """
    Получает все настраиваемые параметры сгруппированными по категориям.

    Возвращает:
    - Текущие значения (с учётом переопределений из БД)
    - Метаданные для построения формы (тип, диапазон, описание)
    - Группировку по функциональным блокам
    """
    metadata = settings.get_settings_metadata()
    active_values = await config_service.get_all_active()

    # Группировка
    groups: dict[str, list[SettingResponse]] = {
        "computer_vision": [],
        "verification": [],
        "uploads": [],
        "packing": [],
    }

    for key in settings.get_dynamic_settings_keys():
        if key not in metadata:
            continue
        meta = metadata[key]
        value = active_values.get(key, getattr(settings, key, None))

        # Форматирование значения для UI
        display_value = value
        if meta.get("multiplier"):
            display_value = value * \
                meta["multiplier"] if isinstance(
                    value, (int, float)) else value

        setting = SettingResponse(
            key=key,
            label=meta["label"],
            type=meta["type"],
            value=value,
            display_value=display_value,
            unit=meta.get("unit", ""),
            description=meta["description"],
            min=getattr(settings.__fields__.get(key), "ge", None) if hasattr(
                settings, "__fields__") else None,
            max=getattr(settings.__fields__.get(key), "le", None) if hasattr(
                settings, "__fields__") else None,
            step=meta.get("step"),
        )
        groups[meta["group"]].append(setting)

    return SettingsGroupResponse(groups=groups)


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_SETTINGS))],
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    """Получает конкретную настройку по ключу."""
    if key not in settings.get_dynamic_settings_keys():
        raise HTTPException(
            status_code=404,
            detail=f"Настройка '{key}' не найдена или не доступна для изменения"
        )

    value = await config_service.get(key)
    metadata = settings.get_settings_metadata().get(key, {})

    display_value = value
    if metadata.get("multiplier"):
        display_value = value * \
            metadata["multiplier"] if isinstance(
                value, (int, float)) else value

    return SettingResponse(
        key=key,
        label=metadata.get("label", key),
        type=metadata.get("type", "str"),
        value=value,
        display_value=display_value,
        unit=metadata.get("unit", ""),
        description=metadata.get("description", ""),
    )


@router.get("/", response_model=SettingsGroupResponse)
async def list_settings(
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_SETTINGS))],
    config_service: Annotated[ConfigService, Depends(get_config_service)],
):
    metadata = settings.get_settings_metadata()
    active_values = await config_service.get_all_active()

    groups: dict[str, list[SettingResponse]] = {
        "computer_vision": [],
        "verification": [],
        "uploads": [],
        "packing": [],
    }

    for key in settings.get_dynamic_settings_keys():
        if key not in metadata:
            continue
        meta = metadata[key]
        value = active_values.get(key, getattr(settings, key, None))

        display_value = value
        if meta.get("multiplier"):
            display_value = value * meta["multiplier"] if isinstance(value, (int, float)) else value

        # Get min/max from Pydantic v2 model fields
        field = settings.model_fields.get(key)
        min_val = field.ge if field and hasattr(field, 'ge') else None
        max_val = field.le if field and hasattr(field, 'le') else None

        setting = SettingResponse(
            key=key,
            label=meta["label"],
            type=meta["type"],
            value=value,
            display_value=display_value,
            unit=meta.get("unit", ""),
            description=meta["description"],
            min=min_val,
            max=max_val,
            step=meta.get("step"),
        )
        groups[meta["group"]].append(setting)

    return SettingsGroupResponse(groups=groups)


@router.patch("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    payload: SettingUpdateRequest,
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_SETTINGS))],
    config_service: Annotated[ConfigService, Depends(get_config_service)],
    settings_repo: Annotated[SettingsRepository, Depends(get_settings_repo)],
):
    if key not in settings.get_dynamic_settings_keys():
        raise HTTPException(status_code=404, detail=f"Настройка '{key}' не найдена или не доступна для изменения")

    metadata = settings.get_settings_metadata().get(key, {})
    expected_type = metadata.get("type")
    value = payload.value

    # Validate range for numeric values
    if expected_type == "float" and isinstance(value, (int, float)):
        field = settings.model_fields.get(key)
        if field:
            if field.ge is not None and value < field.ge:
                raise HTTPException(422, f"Значение ниже минимума ({field.ge})")
            if field.le is not None and value > field.le:
                raise HTTPException(422, f"Значение выше максимума ({field.le})")

    await settings_repo.upsert_setting(
        key=key,
        value_type=expected_type or "str",
        value=payload.value,
        updated_by=current_user.id,
        change_reason=payload.change_reason,
    )

    config_service.invalidate_cache(key)

    logger.info("Настройка '%s' изменена на %s (user_id=%d, reason=%s)",
                key, payload.value, current_user.id, payload.change_reason or "не указано")

    updated_value = await config_service.get(key)
    display_value = updated_value
    if metadata.get("multiplier"):
        display_value = updated_value * metadata["multiplier"] if isinstance(updated_value, (int, float)) else value

    return SettingResponse(
        key=key,
        label=metadata.get("label", key),
        type=expected_type or "str",
        value=updated_value,
        display_value=display_value,
        unit=metadata.get("unit", ""),
        description=metadata.get("description", ""),
    )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_setting(
    key: str,
    current_user: Annotated[User, Depends(require_permission(Permission.MANAGE_SETTINGS))],
    config_service: Annotated[ConfigService, Depends(get_config_service)],
    settings_repo: Annotated[SettingsRepository, Depends(get_settings_repo)],
):
    """
    Сбрасывает настройку к значению по умолчанию из config.
    """
    if key not in settings.get_dynamic_settings_keys():
        raise HTTPException(
            status_code=404,
            detail=f"Настройка '{key}' не найдена"
        )

    deleted = await settings_repo.delete_setting(key)
    if deleted:
        config_service.invalidate_cache(key)
        logger.info("Настройка '%s' сброшена к default (user_id=%d)",
                    key, current_user.id)

    return None
