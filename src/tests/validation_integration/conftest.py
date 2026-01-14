from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]

_engine: AsyncEngine | None = None
_async_session_factory: sessionmaker[AsyncSession] | None = None


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create engine once per test session in the same event loop."""
    global _engine, _async_session_factory
    if _engine is None:
        database_url = os.getenv(
            "DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/agent_router"
        )
        _engine = create_async_engine(
            database_url,
            poolclass=NullPool,
            echo_pool=False,
            connect_args={"server_settings": {"application_name": "agent-orchestration-core-test"}},
        )
        _async_session_factory = sessionmaker(
            bind=_engine, expire_on_commit=False, class_=AsyncSession
        )
    yield _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncSession:
    """Yield a database session per test, created in the same event loop."""
    _, session_factory = test_engine
    async with session_factory() as session:
        try:
            yield session
            if session.in_transaction():
                await session.commit()
        except Exception:
            if session.in_transaction():
                await session.rollback()
            raise
        finally:
            await session.close()
