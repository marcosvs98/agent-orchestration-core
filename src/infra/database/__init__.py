from contextlib import asynccontextmanager
from collections.abc import Callable
from contextlib import _AsyncGeneratorContextManager
from typing import NewType
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from infra.database.json_serialization import jsonb_serializer
from infra.database.models.base import ORMBaseModel
from settings import DATABASE_URL
from adapters.observability.logging import EnvironmentSet, ENVIRONMENT

DbSession = NewType("DbSession", _AsyncGeneratorContextManager[AsyncSession])
ContextDBSession = Callable[[], _AsyncGeneratorContextManager[AsyncSession]]


engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo_pool=False,
    pool_reset_on_return="rollback",
    json_serializer=jsonb_serializer,
    connect_args={"server_settings": {"application_name": "agent-orchestration-core"}},
)
async_session = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class DatabaseConnection:
    def __init__(self, engine: AsyncEngine, sessionmaker: sessionmaker) -> None:
        self.engine = engine
        self.sessionmaker = sessionmaker

    @asynccontextmanager
    async def get_session(self) -> _AsyncGeneratorContextManager[AsyncSession]:  # type: ignore[misc]
        """Get database session as async context manager."""
        session: AsyncSession
        async with self.sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception as exc:
                await session.rollback()
                raise exc from exc
            finally:
                try:
                    await session.rollback()
                except Exception:
                    pass
                await session.close()


@asynccontextmanager  # type: ignore[arg-type]
async def get_db() -> _AsyncGeneratorContextManager[AsyncSession]:  # type: ignore[misc]
    session: AsyncSession
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc from exc
        finally:
            try:
                await session.rollback()
            except Exception:
                pass
            await session.close()


async def create_db() -> None:
    if ENVIRONMENT == EnvironmentSet.DEVELOPMENT:
        async with engine.begin() as conn:
            await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(ORMBaseModel.metadata.create_all)


async def drop_db() -> None:
    if ENVIRONMENT == EnvironmentSet.DEVELOPMENT:
        async with engine.begin() as conn:
            await conn.run_sync(ORMBaseModel.metadata.drop_all)
