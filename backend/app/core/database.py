"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import get_settings

settings = get_settings()

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

# Sync engine for Celery workers
sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,
    pool_pre_ping=True,
)

# Session factories
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

SyncSessionLocal = sessionmaker(
    sync_engine,
    expire_on_commit=False,
)

# Base class for models
Base = declarative_base()


async def get_async_session() -> AsyncSession:
    """Get async database session for FastAPI dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_session():
    """Get sync database session for Celery workers."""
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
