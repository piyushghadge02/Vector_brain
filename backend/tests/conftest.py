"""Shared pytest fixtures.

Integration tests expect a real PostgreSQL + pgvector database with
migrations applied. Point DATABASE_URL at it before running pytest, e.g.::

    DATABASE_URL=postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain_test \\
        alembic upgrade head
    DATABASE_URL=postgresql+asyncpg://.../vectorbrain_test pytest
"""

import os

import pytest
from fastapi.testclient import TestClient

# Must be set before app.config is imported (settings are cached).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://vectorbrain:vectorbrain@localhost:5432/vectorbrain_test",
)

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # Context-manager form runs the app lifespan (engine creation/disposal).
    with TestClient(create_app()) as c:
        yield c
