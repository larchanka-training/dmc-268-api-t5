from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def to_async_url(url: str) -> str:
    """Accept plain ``postgresql://`` URLs (e.g. from docker-compose)."""
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


def create_engine(url: str | None = None) -> AsyncEngine:
    return create_async_engine(
        to_async_url(url or get_settings().database_url.get_secret_value()),
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """One short transaction per scope; external API calls stay outside."""
    async with factory() as session, session.begin():
        yield session
