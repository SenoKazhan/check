import logging
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.settings import SystemSetting

logger = logging.getLogger(__name__)


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_setting(self, key: str) -> Optional[SystemSetting]:
        result = await self.session.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def get_all_settings(self) -> dict[str, SystemSetting]:
        result = await self.session.execute(select(SystemSetting))
        return {s.key: s for s in result.scalars().all()}

    async def upsert_setting(
        self,
        key: str,
        value_type: str,
        value: bool | int | float | str,
        updated_by: int,
        change_reason: Optional[str] = None,
    ) -> SystemSetting:
        value_str = str(value) if not isinstance(value, bool) else str(value).lower()
        existing = await self.get_setting(key)
        if existing:
            await self.session.execute(
                update(SystemSetting)
                .where(SystemSetting.key == key)
                .values(
                    value_type=value_type,
                    value_str=value_str,
                    updated_by=updated_by,
                    change_reason=change_reason,
                )
            )
            await self.session.commit()
            logger.info("Обновлена настройка '%s' (user_id=%d)", key, updated_by)
            return existing
        else:
            new_setting = SystemSetting(
                key=key,
                value_type=value_type,
                value_str=value_str,
                updated_by=updated_by,
                change_reason=change_reason,
            )
            self.session.add(new_setting)
            await self.session.commit()
            logger.info("Создана настройка '%s' (user_id=%d)", key, updated_by)
            return new_setting

    async def delete_setting(self, key: str) -> bool:
        result = await self.session.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            await self.session.delete(setting)
            await self.session.commit()
            logger.info("Удалена настройка '%s' (сброс к default)", key)
            return True
        return False