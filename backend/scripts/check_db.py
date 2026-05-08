"""
Скрипт инициализации БД для тестирования.
Запускает миграции и создаёт тестового пользователя.
"""

import asyncio
import asyncpg
import bcrypt
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import settings
from app.db.manager import DatabaseManager


async def init_db():
    """Создание пула, применение миграций, создание тестового пользователя."""
    
    # 1. Создаём пул
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    db = DatabaseManager(pool)
    
    try:
        # 2. Проверка подключения
        if not await db.ping():
            print("❌ Не удалось подключиться к БД")
            return
        
        print("✅ Подключение к БД успешно")
        
        # 3. Создаём тестового пользователя (если нет)
        test_login = "test_worker"
        user = await db.get_user_by_login(test_login)
        
        if not user:
            password = "test123"
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(settings.bcrypt_cost)).decode()
            user_id = await db.create_user(test_login, password_hash, role="worker")
            print(f"✅ Создан тестовый пользователь: {test_login} (id={user_id})")
        else:
            print(f"ℹ️  Пользователь {test_login} уже существует")
        
        # 4. Создаём тестовый товар
        test_product = {
            "name": "Тестовая коробка",
            "qr_code": "TEST-QR-001",
            "ref_length_mm": 200.0,
            "ref_width_mm": 150.0,
            "ref_height_mm": 100.0,
            "notes": "Создано скриптом init_db.py"
        }
        product = await db.get_product_by_qr(test_product["qr_code"])
        
        if not product:
            prod_id = await db.insert_product(test_product)
            print(f"✅ Создан тестовый товар: {test_product['name']} (id={prod_id})")
        else:
            print(f"ℹ️  Товар {test_product['qr_code']} уже существует")
        
        print("\n🎉 Инициализация завершена успешно!")
        
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(init_db())