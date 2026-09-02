"""Behavioural tests for ContentModeration node."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes.content_moderation import (
    ContentModeration,
)
from domain.execution.services.graph_runtime.types import ExecutionContext
from domain.llm.schemas.moderation import ModerationResult


def _ctx() -> ExecutionContext:
    return ExecutionContext.model_validate(
        {
            "tenant_id": uuid4(),
            "interaction_id": uuid4(),
            "user_id": "u",
            "session_id": uuid4(),
            "input_payload": {"user_input": "hello"},
            "flow_id": uuid4(),
            "flow_version_id": uuid4(),
            "flow_run_id": uuid4(),
            "correlation_id": uuid4(),
            "current_node_id": "n",
            "metadata": {
                "runtime_policy": {
                    "moderation": {"threshold": 0.5},
                }
            },
        }
    )


@pytest.fixture
def tracer() -> MagicMock:
    t = MagicMock(spec=RuntimeTracerPort)
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


@pytest.mark.asyncio
async def test_execute_calls_provider_and_returns_flags(tracer: MagicMock) -> None:
    provider = MagicMock()
    provider.moderate = AsyncMock(
        return_value=ModerationResult(flagged=True, categories={"x": {"y": True}})
    )
    node = ContentModeration(tracer=tracer, llm_moderation_provider=provider)
    out = await node.execute(_ctx(), config={"extra": 1})
    assert out.data["flagged"] is True
    provider.moderate.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_config_merges_runtime_policy_and_call_config(
    tracer: MagicMock,
) -> None:
    provider = MagicMock()
    provider.moderate = AsyncMock(return_value=ModerationResult(flagged=False, categories={}))
    node = ContentModeration(tracer=tracer, llm_moderation_provider=provider)
    ctx = _ctx()
    await node.execute(ctx, config={"call_only": True})
    call_kw = provider.moderate.await_args
    cfg = call_kw.kwargs["config"]
    assert cfg.get("threshold") == 0.5
    assert cfg.get("call_only") is True
