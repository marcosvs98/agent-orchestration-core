"""Behavioural coverage for execution observability hooks (Composite, DB, memory extraction)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.services.observability.hooks import (
    CompositeHook,
    DbExecutionEventHook,
    ExecutionEventHook,
    MemoryExtractionHook,
)


def _tracer() -> MagicMock:
    t = MagicMock()
    h = MagicMock()
    h.success = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(h)
    return t


class _OkHook(ExecutionEventHook):
    async def on_flow_start(self, **kwargs: object) -> None:
        return None

    async def on_node_start(self, **kwargs: object) -> None:
        return None

    async def on_node_complete(self, **kwargs: object) -> None:
        return None

    async def on_edge_evaluated(self, **kwargs: object) -> None:
        return None

    async def on_flow_complete(self, **kwargs: object) -> None:
        return None

    async def on_flow_failed(self, **kwargs: object) -> None:
        return None


class _FailHook(ExecutionEventHook):
    def __init__(self, msg: str = "boom") -> None:
        self._msg = msg

    async def on_flow_start(self, **kwargs: object) -> None:
        raise RuntimeError(self._msg)

    async def on_node_start(self, **kwargs: object) -> None:
        raise RuntimeError(self._msg)

    async def on_node_complete(self, **kwargs: object) -> None:
        raise RuntimeError(self._msg)

    async def on_edge_evaluated(self, **kwargs: object) -> None:
        raise RuntimeError(self._msg)

    async def on_flow_complete(self, **kwargs: object) -> None:
        raise RuntimeError(self._msg)

    async def on_flow_failed(self, **kwargs: object) -> None:
        raise RuntimeError(self._msg)


@pytest.mark.asyncio
async def test_composite_propagates_first_subscriber_error() -> None:
    comp = CompositeHook([_FailHook(), _OkHook()])
    with pytest.raises(RuntimeError, match="boom"):
        await comp.on_flow_start()


@pytest.mark.asyncio
async def test_composite_swallows_second_subscriber_failure() -> None:
    comp = CompositeHook([_OkHook(), _FailHook()])
    await comp.on_flow_start()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "on_flow_start",
        "on_node_start",
        "on_node_complete",
        "on_edge_evaluated",
        "on_flow_complete",
        "on_flow_failed",
    ],
)
async def test_composite_first_fail_each_method(method: str) -> None:
    comp = CompositeHook([_FailHook("x"), _OkHook()])
    with pytest.raises(RuntimeError, match="x"):
        await getattr(comp, method)()


@pytest.mark.asyncio
async def test_db_hook_emits_all_lifecycle_events() -> None:
    repo = MagicMock()
    repo.append_execution_event = AsyncMock(return_value=uuid4())
    hook = DbExecutionEventHook(repository=repo, tracer=_tracer())
    tid, sid, fid, cid = uuid4(), uuid4(), uuid4(), uuid4()
    nid = uuid4()
    await hook.on_flow_start(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={"a": 1},
    )
    await hook.on_node_start(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        node_id=nid,
        payload={"b": 2},
    )
    await hook.on_node_complete(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        node_id=nid,
        payload={"c": 3},
    )
    await hook.on_edge_evaluated(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        node_id=nid,
        edge_id="e1",
        payload={"d": 4},
    )
    await hook.on_flow_complete(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={"e": 5},
    )
    await hook.on_flow_failed(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={"f": 6},
    )
    assert repo.append_execution_event.await_count == 6


@pytest.mark.asyncio
async def test_db_hook_safe_emit_swallows_repository_error() -> None:
    repo = MagicMock()
    repo.append_execution_event = AsyncMock(side_effect=ValueError("db"))
    hook = DbExecutionEventHook(repository=repo, tracer=_tracer())
    tid, sid, fid, cid = uuid4(), uuid4(), uuid4(), uuid4()
    await hook.on_flow_start(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={},
    )


@pytest.mark.asyncio
async def test_memory_extraction_hook_skips_when_types_invalid() -> None:
    base = MagicMock(spec=ExecutionEventHook)
    base.on_flow_complete = AsyncMock()
    proc = MagicMock()
    proc.execute = AsyncMock()
    hook = MemoryExtractionHook(
        base_hook=base,
        memory_extraction_processor=proc,
        tracer=_tracer(),
    )
    await hook.on_flow_complete(
        tenant_id="not-uuid",
        user_id="u",
        session_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        payload={},
    )
    proc.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_extraction_coerces_non_dict_flow_output_to_empty_dict() -> None:
    base = MagicMock(spec=ExecutionEventHook)
    base.on_flow_complete = AsyncMock()
    proc = MagicMock()
    proc.execute = AsyncMock()
    hook = MemoryExtractionHook(
        base_hook=base,
        memory_extraction_processor=proc,
        tracer=_tracer(),
    )
    tid, sid, fid, cid = uuid4(), uuid4(), uuid4(), uuid4()
    await hook.on_flow_complete(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={
            "payload": ["not", "dict"],
            "memory_extraction_config": {"k": "v"},
        },
    )
    proc.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_extraction_hook_runs_processor() -> None:
    base = MagicMock(spec=ExecutionEventHook)
    base.on_flow_complete = AsyncMock()
    proc = MagicMock()
    proc.execute = AsyncMock()
    hook = MemoryExtractionHook(
        base_hook=base,
        memory_extraction_processor=proc,
        tracer=_tracer(),
    )
    tid, sid, uid, fid, cid = uuid4(), uuid4(), "user", uuid4(), uuid4()
    await hook.on_flow_complete(
        tenant_id=tid,
        user_id=uid,
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={
            "payload": {"out": 1},
            "memory_extraction_config": {"k": "v"},
        },
    )
    proc.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_extraction_hook_swallows_processor_error() -> None:
    base = MagicMock(spec=ExecutionEventHook)
    base.on_flow_complete = AsyncMock()
    proc = MagicMock()
    proc.execute = AsyncMock(side_effect=RuntimeError("x"))
    hook = MemoryExtractionHook(
        base_hook=base,
        memory_extraction_processor=proc,
        tracer=_tracer(),
    )
    tid, sid, fid, cid = uuid4(), uuid4(), uuid4(), uuid4()
    await hook.on_flow_complete(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={
            "payload": {},
            "memory_extraction_config": {"a": 1},
        },
    )


@pytest.mark.asyncio
async def test_memory_extraction_delegates_other_events() -> None:
    base = MagicMock(spec=ExecutionEventHook)
    for name in (
        "on_flow_start",
        "on_node_start",
        "on_node_complete",
        "on_edge_evaluated",
        "on_flow_failed",
    ):
        setattr(base, name, AsyncMock())
    proc = MagicMock()
    proc.execute = AsyncMock()
    hook = MemoryExtractionHook(
        base_hook=base,
        memory_extraction_processor=proc,
        tracer=_tracer(),
    )
    await hook.on_flow_start()
    await hook.on_node_start()
    await hook.on_node_complete()
    await hook.on_edge_evaluated()
    await hook.on_flow_failed()
    base.on_flow_start.assert_awaited_once()
    base.on_node_start.assert_awaited_once()
    base.on_node_complete.assert_awaited_once()
    base.on_edge_evaluated.assert_awaited_once()
    base.on_flow_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_extraction_returns_when_config_not_dict() -> None:
    base = MagicMock(spec=ExecutionEventHook)
    base.on_flow_complete = AsyncMock()
    proc = MagicMock()
    proc.execute = AsyncMock()
    hook = MemoryExtractionHook(
        base_hook=base,
        memory_extraction_processor=proc,
        tracer=_tracer(),
    )
    tid, sid, fid, cid = uuid4(), uuid4(), uuid4(), uuid4()
    await hook.on_flow_complete(
        tenant_id=tid,
        user_id="u",
        session_id=sid,
        flow_run_id=fid,
        correlation_id=cid,
        payload={
            "payload": {},
            "memory_extraction_config": "bad",
        },
    )
    proc.execute.assert_not_awaited()
