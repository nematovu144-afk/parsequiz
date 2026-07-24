"""Shared pytest fixtures: an isolated in-memory SQLite DB per test."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import limiter
from app.db import base as db_base
from app.db.base import Base


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """slowapi's counters live in process memory and persist across tests
    otherwise — an autouse reset keeps /api/upload's 10/minute cap from
    making test order/count affect results."""
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def test_db(monkeypatch):
    """Point app.db.base.async_session_factory at a fresh in-memory DB.

    StaticPool + check_same_thread=False: SQLite ':memory:' is otherwise
    per-connection, so the async pool would hand each session a blank DB.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_base, "async_session_factory", session_factory)

    yield

    await engine.dispose()
