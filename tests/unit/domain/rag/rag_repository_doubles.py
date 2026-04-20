"""Test doubles for RagRepository unit tests — typed mocks (spec=) and session wiring."""

from __future__ import annotations

import contextlib
from contextlib import AbstractAsyncContextManager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.cache.redis_adapter import RedisAdapter
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.rag.repositories.rag_repository import RagRepository
from infra.database import DatabaseConnection
from infra.database.models.rag.rag_chunk import RagChunk as RagChunkModel
from infra.database.models.rag.rag_config import RagConfig as RagConfigModel
from infra.database.models.rag.rag_document import RagDocument as RagDocumentModel
from infra.database.models.rag.rag_query_cache import (
    RagQueryCache as RagQueryCacheModel,
)


def runtime_tracer_double() -> MagicMock:
    """Minimal RuntimeTracerPort double: observe() returns a disposable context manager."""
    tracer = MagicMock(spec=RuntimeTracerPort)
    handle = MagicMock()
    handle.success = MagicMock()
    tracer.observe.side_effect = lambda **_: contextlib.nullcontext(handle)
    return tracer


def redis_adapter_double() -> MagicMock:
    cache = MagicMock(spec=RedisAdapter)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return cache


def database_connection_double() -> MagicMock:
    return MagicMock(spec=DatabaseConnection)


def async_session_double() -> AsyncMock:
    """AsyncSession used as a test double; configure execute / add / commit as needed."""
    return AsyncMock(spec=AsyncSession)


def session_context(session: AsyncMock) -> MagicMock:
    """Async context manager returned by DatabaseConnection.get_session()."""
    cm = MagicMock(spec=AbstractAsyncContextManager)
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def bind_rag_session(repo: RagRepository, session: AsyncMock) -> None:
    repo.db.get_session = MagicMock(return_value=session_context(session))


def make_rag_repository(*, with_tracer: bool = True) -> RagRepository:
    db = database_connection_double()
    cache = redis_adapter_double()
    tracer = runtime_tracer_double() if with_tracer else None
    return RagRepository(db, tracer=tracer, cache_adapter=cache)


def execute_result_scalar_one(value: Any | None) -> MagicMock:
    res = MagicMock(spec=Result)
    res.scalar_one_or_none = MagicMock(return_value=value)
    return res


def execute_result_scalars_all(rows: list[Any]) -> MagicMock:
    res = MagicMock(spec=Result)
    scalars = MagicMock()
    scalars.all.return_value = rows
    res.scalars.return_value = scalars
    return res


def execute_result_all(rows: list[Any]) -> MagicMock:
    res = MagicMock(spec=Result)
    res.all.return_value = rows
    return res


def execute_result_scalar(value: Any | None) -> MagicMock:
    res = MagicMock(spec=Result)
    res.scalar = MagicMock(return_value=value)
    return res


def execute_result_rowcount(n: int) -> MagicMock:
    res = MagicMock(spec=Result)
    res.rowcount = n
    return res


def nested_transaction_context() -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def rag_chunk_model_double(**attrs: Any) -> MagicMock:
    ch = MagicMock(spec=RagChunkModel)
    for k, v in attrs.items():
        setattr(ch, k, v)
    return ch


def rag_config_model_double(**attrs: Any) -> MagicMock:
    m = MagicMock(spec=RagConfigModel)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def rag_document_model_double(**attrs: Any) -> MagicMock:
    m = MagicMock(spec=RagDocumentModel)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def rag_query_cache_model_double(**attrs: Any) -> MagicMock:
    m = MagicMock(spec=RagQueryCacheModel)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m
