from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=20, max_overflow=10)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


# --- Sync engine for Celery tasks and sync endpoints ---
# Shared singleton to avoid creating a new engine per request/task

_sync_engine = None


def get_sync_engine():
    """Return a synchronous SQLAlchemy engine for use in Celery tasks and sync endpoints.

    Lazily initialized and cached as a module-level singleton.
    Converts the asyncpg URL to psycopg2 for sync operations.
    Uses pool_pre_ping for resilience against dropped connections.
    """
    global _sync_engine
    if _sync_engine is None:
        url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        _sync_engine = create_engine(url, pool_pre_ping=True)
    return _sync_engine


def dispose_sync_engine():
    """Dispose the sync engine connection pool. Call on shutdown."""
    global _sync_engine
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None
