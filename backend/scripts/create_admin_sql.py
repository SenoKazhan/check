import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.auth.manager import AuthManager
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine(settings.database_url)
    
    async with engine.begin() as conn:
        print("🗑️  Удаляю старую таблицу users...")
        await conn.execute(text("DROP TABLE IF EXISTS users CASCADE"))
        
        print("🏗️  Создаю новую таблицу users по ТЗ...")
        await conn.execute(text("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                login VARCHAR(64) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(10) NOT NULL CHECK (role IN ('worker', 'admin')),
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        
        # Создаем админа
        email = "admin@warehouse.dev" # Используем как login
        password = "admin123"
        hashed = AuthManager.hash_password(password)
        
        print(f"👤 Создаю админа: {email}...")
        await conn.execute(
            text("INSERT INTO users (login, password_hash, role) VALUES (:login, :hash, 'admin')"),
            {"login": email, "hash": hashed}
        )
        
        print("✅ Готово! Таблица создана, админ добавлен.")
        print(f"   Логин: {email}")
        print(f"   Пароль: {password}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())