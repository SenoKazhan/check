import asyncio
import sys
from pathlib import Path

# Добавляем backend в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def create_admin():
    print("Connecting to database...")
    engine = create_async_engine(settings.database_url, echo=True)
    
    async with engine.begin() as conn:
        # Проверяем существование пользователя
        print("Checking if admin exists...")
        result = await conn.execute(text("SELECT id FROM users WHERE login = 'admin'"))
        user = result.fetchone()
        
        if user:
            print(f"Admin already exists with id: {user[0]}")
            # Обновим пароль
            new_hash = pwd_context.hash('admin123')
            await conn.execute(
                text("UPDATE users SET password_hash = :hash WHERE login = 'admin'"),
                {"hash": new_hash}
            )
            print("Password updated for admin")
        else:
            # Создаем нового админа
            print("Creating new admin user...")
            password_hash = pwd_context.hash('admin123')
            await conn.execute(
                text("INSERT INTO users (login, password_hash, role) VALUES ('admin', :hash, 'admin')"),
                {"hash": password_hash}
            )
            print("✓ Admin user created successfully!")
        
        # Проверяем созданного пользователя
        result = await conn.execute(text("SELECT id, login, role FROM users WHERE login = 'admin'"))
        admin = result.fetchone()
        if admin:
            print(f"Verification: id={admin[0]}, login={admin[1]}, role={admin[2]}")
    
    await engine.dispose()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(create_admin())