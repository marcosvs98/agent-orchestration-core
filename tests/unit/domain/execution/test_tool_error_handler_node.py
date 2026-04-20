"""Behavioural tests for ToolErrorHandlerNode (retry vs finalize vs legacy shapes)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.nodes.tool_error_handler import (
    ToolErrorHandlerNode,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    OperationStatus,
)
from domain.prompts.schemas.prompt import NodeType


def _base_context(**kwargs: object) -> ExecutionContext:
    defaults: dict[str, object] = {
        "tenant_id": uuid4(),
        "interaction_id": uuid4(),
        "user_id": "u1",
        "session_id": uuid4(),
        "input_payload": None,
        "flow_id": uuid4(),
        "flow_version_id": uuid4(),
        "flow_run_id": uuid4(),
        "correlation_id": uuid4(),
        "current_node_id": "n1",
    }
    defaults.update(kwargs)
    return ExecutionContext.model_validate(defaults)


@pytest.mark.asyncio
async def test_empty_results_returns_empty_payload() -> None:
    node = ToolErrorHandlerNode()
    ctx = _base_context(
        state={},
    )
    ctx.state[NodeType.ToolExecutor.value] = {"result": "not-a-list"}
    out = await node.execute(ctx, config={})
    assert out.data["retry_operation_ids"] == []
    assert out.data["fallback_required"] is False


@pytest.mark.asyncio
async def test_retries_when_under_max_and_retryable_status() -> None:
    node = ToolErrorHandlerNode()
    op = str(uuid4())
    ctx = _base_context(
        state={"retry_counts": {}},
    )
    ctx.state[NodeType.ToolExecutor.value] = {
        "result": [
            {
                "operation_id": op,
                "status": OperationStatus.ERROR.value,
            }
        ]
    }
    out = await node.execute(ctx, config={"max_retries": 2})
    assert op in out.data["retry_operation_ids"]
    assert out.next_state is not None
    assert out.next_state["retry_counts"][op] == 1


@pytest.mark.asyncio
async def test_fallback_when_exhausted_retries() -> None:
    node = ToolErrorHandlerNode()
    op = str(uuid4())
    ctx = _base_context(
        state={"retry_counts": {op: 2}},
    )
    res = {"operation_id": op, "status": OperationStatus.ERROR.value}
    ctx.state[NodeType.ToolExecutor.value] = {"result": [res]}
    out = await node.execute(ctx, config={"max_retries": 2})
    assert op not in out.data["retry_operation_ids"]
    assert out.data["fallback_required"] is True
    assert res in out.data["finalized_results"]


@pytest.mark.asyncio
async def test_legacy_results_key_from_node_output() -> None:
    node = ToolErrorHandlerNode()
    op = str(uuid4())
    ctx = _base_context(state={}, node_output={"results": [{"operation_id": op, "status": "ok"}]})
    ctx.state[NodeType.ToolExecutor.value] = {}
    out = await node.execute(ctx, {})
    assert out.data["finalized_results_count"] >= 1


@pytest.mark.asyncio
async def test_invalid_max_retries_coerces_to_zero() -> None:
    node = ToolErrorHandlerNode()
    op = str(uuid4())
    ctx = _base_context(state={})
    ctx.state[NodeType.ToolExecutor.value] = {
        "result": [{"operation_id": op, "status": OperationStatus.ERROR.value}]
    }
    out = await node.execute(ctx, config={"max_retries": "not-int"})
    assert out.data["retry_operation_ids"] == []
