"""
Async SQLAlchemy engine and session factory.
Import get_async_session in FastAPI dependencies for request-scoped sessions.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config.settings import get_settings

settings = get_settings()

# Create the async engine once at module level (connection pool)
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,  # Log SQL in dev
    pool_pre_ping=True,            # Verify connections before use
    pool_size=10,
    max_overflow=20,
)

# Session factory — use async_sessionmaker (SQLAlchemy 2.0+)
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Avoid lazy-load errors after commit
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a per-request database session.
    Session is automatically closed after the request.
    """
    async with AsyncSessionFactory() as session:
        yield session
