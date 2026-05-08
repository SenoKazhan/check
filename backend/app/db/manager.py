"""
Модуль базы данных: Repository-паттерн для инкапсуляции операций с PostgreSQL.
Все запросы параметризованы, используется asyncpg, логирование через logging.
"""

import logging
from typing import Optional, Dict, Any, List
import asyncpg

from app.core.config import settings
from app.db.models import Measurement, PackingSession, PackingResult, Product, User
from app.schemas import MeasureResult, VerifyResult, PackResult, Placement

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Repository для работы с базой данных.
    Инкапсулирует все операции чтения/записи, защищает от SQL-инъекций.
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        :param pool: Пул асинхронных соединений asyncpg.
        """
        self.pool = pool

    # ─────────────────────────────────────────────────────────────────
    # ПОЛЬЗОВАТЕЛИ
    # ─────────────────────────────────────────────────────────────────
    async def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        """Поиск пользователя по логину. Возвращает dict или None."""
        row = await self.pool.fetchrow(
            """
            SELECT id, login, password_hash, role, created_at
            FROM users
            WHERE login = $1
            """,
            login,
        )
        return dict(row) if row else None

    async def create_user(
        self, login: str, password_hash: str, role: str = "worker"
    ) -> int:
        """Создание нового пользователя. Возвращает id."""
        row = await self.pool.fetchrow(
            """
            INSERT INTO users (login, password_hash, role)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            login,
            password_hash,
            role,
        )
        return row["id"]

    # ─────────────────────────────────────────────────────────────────
    # ТОВАРЫ (СПРАВОЧНИК)
    # ─────────────────────────────────────────────────────────────────
    async def get_product_by_qr(self, qr_code: str) -> Optional[Dict[str, Any]]:
        """Поиск товара по QR-коду. Возвращает dict или None."""
        row = await self.pool.fetchrow(
            """
            SELECT id, name, qr_code, ref_length_mm, ref_width_mm, ref_height_mm, notes
            FROM products
            WHERE qr_code = $1
            """,
            qr_code,
        )
        return dict(row) if row else None

    async def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Поиск товара по id. Возвращает dict или None."""
        row = await self.pool.fetchrow(
            """
            SELECT id, name, qr_code, ref_length_mm, ref_width_mm, ref_height_mm, notes
            FROM products
            WHERE id = $1
            """,
            product_id,
        )
        return dict(row) if row else None

    async def insert_product(self, data: Dict[str, Any]) -> int:
        """Добавление товара в справочник. Возвращает id."""
        row = await self.pool.fetchrow(
            """
            INSERT INTO products 
            (name, qr_code, ref_length_mm, ref_width_mm, ref_height_mm, notes)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            data["name"],
            data.get("qr_code"),
            data.get("ref_length_mm"),
            data.get("ref_width_mm"),
            data.get("ref_height_mm"),
            data.get("notes"),
        )
        return row["id"]

    async def update_product(self, product_id: int, data: Dict[str, Any]) -> bool:
        """Обновление товара. Возвращает True, если запись найдена."""
        result = await self.pool.execute(
            """
            UPDATE products
            SET name = COALESCE($2, name),
                qr_code = COALESCE($3, qr_code),
                ref_length_mm = COALESCE($4, ref_length_mm),
                ref_width_mm = COALESCE($5, ref_width_mm),
                ref_height_mm = COALESCE($6, ref_height_mm),
                notes = COALESCE($7, notes)
            WHERE id = $1
            """,
            product_id,
            data.get("name"),
            data.get("qr_code"),
            data.get("ref_length_mm"),
            data.get("ref_width_mm"),
            data.get("ref_height_mm"),
            data.get("notes"),
        )
        return result == "UPDATE 1"

    # ─────────────────────────────────────────────────────────────────
    # ИЗМЕРЕНИЯ (CV-РЕЗУЛЬТАТЫ)
    # ─────────────────────────────────────────────────────────────────
    async def insert_measurement(
        self,
        data: MeasureResult,
        verify: VerifyResult,
        product_id: Optional[int],
        user_id: int,
    ) -> int:
        """
        Сохранение результата измерения и верификации.
        Возвращает id созданной записи.
        """
        row = await self.pool.fetchrow(
            """
            INSERT INTO measurements 
            (product_id, user_id, length_mm, width_mm, height_mm,
             delta_pct, verified_ok, override_reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            product_id,
            user_id,
            data.length_mm,
            data.width_mm,
            data.height_mm,
            verify.delta_pct,
            verify.ok,
            verify.override_reason if verify.overridden else None,
        )
        return row["id"]

    async def get_measurement_by_id(self, measurement_id: int) -> Optional[Dict[str, Any]]:
        """Получение измерения по id."""
        row = await self.pool.fetchrow(
            """
            SELECT * FROM measurements WHERE id = $1
            """,
            measurement_id,
        )
        return dict(row) if row else None

    async def get_measurements_by_session(
        self, session_id: int
    ) -> List[Dict[str, Any]]:
        """
        Получение всех измерений, связанных с сеансом упаковки.
        Используется для отображения списка товаров в сеансе.
        """
        rows = await self.pool.fetch(
            """
            SELECT m.*, p.name as product_name
            FROM measurements m
            JOIN packing_items pi ON m.id = pi.measurement_id
            LEFT JOIN products p ON m.product_id = p.id
            WHERE pi.session_id = $1
            ORDER BY m.measured_at DESC
            """,
            session_id,
        )
        return [dict(r) for r in rows]

    # ─────────────────────────────────────────────────────────────────
    # СЕАНСЫ УПАКОВКИ
    # ─────────────────────────────────────────────────────────────────
    async def create_session(self, user_id: int) -> int:
        """Создание нового сеанса упаковки со статусом 'pending'. Возвращает id."""
        row = await self.pool.fetchrow(
            """
            INSERT INTO packing_sessions (user_id, status)
            VALUES ($1, 'pending')
            RETURNING id
            """,
            user_id,
        )
        return row["id"]

    async def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Получение сеанса по id."""
        row = await self.pool.fetchrow(
            """
            SELECT * FROM packing_sessions WHERE id = $1
            """,
            session_id,
        )
        return dict(row) if row else None

    async def update_session_status(self, session_id: int, status: str) -> bool:
        """Обновление статуса сеанса. Возвращает True, если запись найдена."""
        if status not in ("pending", "done", "error"):
            raise ValueError(f"Invalid status: {status}")
        result = await self.pool.execute(
            """
            UPDATE packing_sessions SET status = $1 WHERE id = $2
            """,
            status,
            session_id,
        )
        return result == "UPDATE 1"

    # ─────────────────────────────────────────────────────────────────
    # ТОВАРЫ В СЕАНСЕ (связь многие-ко-многим)
    # ─────────────────────────────────────────────────────────────────
    async def insert_packing_item(
        self, session_id: int, measurement_id: int, quantity: int = 1
    ) -> None:
        """Добавление товара в сеанс упаковки."""
        await self.pool.execute(
            """
            INSERT INTO packing_items (session_id, measurement_id, quantity)
            VALUES ($1, $2, $3)
            """,
            session_id,
            measurement_id,
            quantity,
        )

    async def get_packing_items_by_session(
        self, session_id: int
    ) -> List[Dict[str, Any]]:
        """Получение списка товаров в сеансе с данными измерений."""
        rows = await self.pool.fetch(
            """
            SELECT pi.*, m.length_mm, m.width_mm, m.height_mm, m.product_id
            FROM packing_items pi
            JOIN measurements m ON pi.measurement_id = m.id
            WHERE pi.session_id = $1
            """,
            session_id,
        )
        return [dict(r) for r in rows]

    # ─────────────────────────────────────────────────────────────────
    # РЕЗУЛЬТАТЫ УПАКОВКИ
    # ─────────────────────────────────────────────────────────────────
    async def insert_packing_result(
        self, data: PackResult, session_id: int, variant_index: int
    ) -> int:
        """
        Сохранение варианта укладки.
        Возвращает id созданной записи.
        """
        import json

        placements_json = json.dumps(
            [
                {
                    "item_id": p.item_id,
                    "x_mm": p.x_mm,
                    "y_mm": p.y_mm,
                    "z_mm": p.z_mm,
                    "rotated": p.rotated,
                }
                for p in data.placements
            ],
            ensure_ascii=False,
        )

        row = await self.pool.fetchrow(
            """
            INSERT INTO packing_results 
            (session_id, variant_index, box_l_mm, box_w_mm, box_h_mm,
             box_volume_cm3, placements_json)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            session_id,
            variant_index,
            data.box_l_mm,
            data.box_w_mm,
            data.box_h_mm,
            data.box_volume_cm3,
            placements_json,
        )
        return row["id"]

    async def get_packing_results_by_session(
        self, session_id: int
    ) -> List[Dict[str, Any]]:
        """Получение всех вариантов укладки для сеанса."""
        rows = await self.pool.fetch(
            """
            SELECT * FROM packing_results
            WHERE session_id = $1
            ORDER BY variant_index ASC
            """,
            session_id,
        )
        return [dict(r) for r in rows]

    async def set_selected_result(self, result_id: int, session_id: int) -> bool:
        """
        Помечает выбранный вариант (selected=TRUE) и сбрасывает остальные.
        Возвращает True, если запись найдена.
        """
        result = await self.pool.execute(
            """
            UPDATE packing_results
            SET selected = (id = $1)
            WHERE session_id = $2
            """,
            result_id,
            session_id,
        )
        return result == "UPDATE 1"

    async def get_selected_result_by_session(
        self, session_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получение выбранного варианта укладки для сеанса."""
        row = await self.pool.fetchrow(
            """
            SELECT * FROM packing_results
            WHERE session_id = $1 AND selected = TRUE
            """,
            session_id,
        )
        return dict(row) if row else None

    # ─────────────────────────────────────────────────────────────────
    # УТИЛИТЫ
    # ─────────────────────────────────────────────────────────────────
    async def close(self) -> None:
        """Закрытие пула соединений."""
        await self.pool.close()
        logger.info("Database pool closed")

    async def ping(self) -> bool:
        """Проверка доступности БД."""
        try:
            await self.pool.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database ping failed: {e}")
            return False


# ─────────────────────────────────────────────────────────────────
# Фабрика для создания экземпляра (удобно для зависимостей FastAPI)
# ─────────────────────────────────────────────────────────────────
async def get_db_manager() -> DatabaseManager:
    """
    Factory для создания DatabaseManager.
    Используется как зависимость в FastAPI.
    """
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return DatabaseManager(pool)