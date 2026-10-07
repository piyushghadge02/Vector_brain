"""Async SQLAlchemy engine + session factory.

The engine is created in the application lifespan (one per event loop) and
stored on ``app.state`` — never at import time. This keeps the engine bound
to the loop that serves requests, which is what makes TestClient-based
integration tests and multi-loop deployments safe.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,  # drop stale connections instead of failing requests
        pool_size=5,
        max_overflow=10,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
