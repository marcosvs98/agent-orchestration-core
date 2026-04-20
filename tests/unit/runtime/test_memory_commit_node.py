from __future__ import annotations

import uuid

import pytest

from domain.execution.services.graph_runtime.nodes.memory_commit import MemoryCommitNode
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
)
from domain.prompts.schemas.prompt import NodeType


def _ctx() -> ExecutionContext:
    tid = uuid.uuid4()
    return ExecutionContext(
        tenant_id=tid,
        interaction_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        input_payload={},
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_memory_commit_node_builds_memory_snapshot() -> None:
    node = MemoryCommitNode()
    rid = uuid.uuid4()
    ctx = _ctx()
    result = await node.execute(
        ctx,
        config={
            "schema_id": "user.preference.v1",
            "schema_version": 1,
            "source": "explicit_user",
            "rag_config_id": str(rid),
            "data": {"preference_key": "k", "preference_value": "v"},
        },
    )
    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.node == NodeType.MemoryCommitNode
    assert result.memory is not None
    assert result.memory == [
        *ctx.memory,
        {
            "schema_id": "user.preference.v1",
            "schema_version": 1,
            "data": {"preference_key": "k", "preference_value": "v"},
            "source": "explicit_user",
            "rag_config_id": str(rid),
        },
    ]


@pytest.mark.asyncio
async def test_memory_commit_node_errors_on_missing_schema() -> None:
    node = MemoryCommitNode()
    result = await node.execute(
        _ctx(),
        config={"rag_config_id": str(uuid.uuid4())},
    )
    assert result.status == NodeExecutionStatus.ERROR


@pytest.mark.asyncio
async def test_memory_commit_node_errors_on_invalid_rag_config_uuid() -> None:
    node = MemoryCommitNode()
    result = await node.execute(
        _ctx(),
        config={"schema_id": "user.preference.v1", "rag_config_id": "not-a-uuid"},
    )
    assert result.status == NodeExecutionStatus.ERROR
