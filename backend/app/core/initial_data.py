import asyncio
import logging
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.user import User

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [INIT] %(levelname)s: %(message)s",
    force=True
)


async def ensure_superuser(session: AsyncSession) -> None:
    stmt = select(User).where(User.login == settings.first_superuser_email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        logger.info("Superuser already exists. Skipping.")
        return

    user = User(
        login=settings.first_superuser_email,
        password_hash=get_password_hash(settings.first_superuser_password),
        role="admin"
    )
    session.add(user)
    await session.commit()
    logger.info("Superuser created successfully.")


async def run_initialization() -> None:
    logger.info("Starting data initialization sequence...")
    try:
        engine = create_async_engine(settings.database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_factory() as session:
            await ensure_superuser(session)

        await engine.dispose()
        logger.info("Data initialization completed.")
    except Exception as error:
        logger.error("Initialization failed: %s", error)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_initialization())