"""Async SQLAlchemy engine, session factory and declarative base."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _engine_kwargs(url: str) -> dict:
    # SQLite (used by the test suite) does not accept pool sizing arguments.
    if url.startswith("sqlite"):
        return {"echo": False}
    return {"echo": False, "pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}


engine = create_async_engine(settings.database_url, **_engine_kwargs(settings.database_url))

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped session."""
    async with SessionLocal() as session:
        yield session
