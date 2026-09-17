"""Factories only: engines are constructed by the caller, not at import time."""

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str | URL) -> tuple[AsyncEngine, async_sessionmaker]:
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("DATABASE_URL must use postgresql+psycopg")
    engine = create_async_engine(url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
