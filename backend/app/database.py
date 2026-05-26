from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=20, max_overflow=10)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for provider API and Celery tasks
sync_engine = create_engine(
    settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://"),
    echo=False,
    pool_size=5,
    max_overflow=5,
)

sync_session_factory = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def get_db_sync() -> Session:
    """Synchronous DB session for provider endpoints and Celery tasks."""
    with sync_session_factory() as session:
        yield session
