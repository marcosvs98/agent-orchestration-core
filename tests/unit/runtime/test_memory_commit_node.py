from __future__ import annotations

import uuid

import pytest

from domain.execution.services.graph_runtime.nodes.memory_commit import MemoryCommitNode
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
)
from domain.prompts.schemas.prompt import NodeType
from exceptions.service_exceptions import BaseServiceException


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


class _Node:
    def __init__(self, allow_memory_write: bool) -> None:
        self.allow_memory_write = allow_memory_write


class _Repo:
    def __init__(self, node: _Node | None) -> None:
        self.node = node

    async def get_node(self, node_id):  # noqa: ANN001, ANN201
        return self.node


class _Writer:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def write_memory_item(self, *, tenant_id, user_id, item, event_context=None):  # noqa: ANN001, ANN201
        self.calls += 1
        if self.error is not None:
            raise self.error
        return None


def _cfg() -> dict:
    return {
        "schema_id": "user.preference.v1",
        "rag_config_id": str(uuid.uuid4()),
        "data": {"preference_key": "k", "preference_value": "v"},
    }


@pytest.mark.asyncio
async def test_memory_commit_reports_persisted_when_write_succeeds() -> None:
    writer = _Writer()
    node = MemoryCommitNode(
        memory_write_service=writer,
        execution_repository=_Repo(_Node(allow_memory_write=True)),
    )
    ctx = _ctx()

    result = await node.execute(
        ctx.model_copy(update={"current_node_run_id": uuid.uuid4()}), _cfg()
    )

    assert writer.calls == 1
    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["persisted"] is True
    assert result.data["memory_commit"] == "persisted"
    assert result.data["reason_code"] == "memory_commit_persisted"


@pytest.mark.asyncio
async def test_memory_commit_reports_write_not_allowed_without_persisting() -> None:
    writer = _Writer()
    node = MemoryCommitNode(
        memory_write_service=writer,
        execution_repository=_Repo(_Node(allow_memory_write=False)),
    )

    result = await node.execute(_ctx(), _cfg())

    assert writer.calls == 0
    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["persisted"] is False
    assert result.data["reason_code"] == "memory_commit_write_not_allowed"


@pytest.mark.asyncio
async def test_memory_commit_fails_when_durable_write_raises() -> None:
    writer = _Writer(error=BaseServiceException(message="memory_quota_exceeded"))
    node = MemoryCommitNode(
        memory_write_service=writer,
        execution_repository=_Repo(_Node(allow_memory_write=True)),
    )

    result = await node.execute(_ctx(), _cfg())

    assert writer.calls == 1
    assert result.status == NodeExecutionStatus.ERROR
    assert result.data["persisted"] is False
    assert result.data["reason_code"] == "memory_commit_write_failed"
    assert result.data["detail"] == "memory_quota_exceeded"


@pytest.mark.asyncio
async def test_memory_commit_fails_when_node_definition_missing() -> None:
    node = MemoryCommitNode(
        memory_write_service=_Writer(),
        execution_repository=_Repo(None),
    )

    result = await node.execute(_ctx(), _cfg())

    assert result.status == NodeExecutionStatus.ERROR
    assert result.data["reason_code"] == "memory_commit_node_not_found"


@pytest.mark.asyncio
async def test_memory_commit_reports_writer_unavailable_when_not_injected() -> None:
    result = await MemoryCommitNode().execute(_ctx(), _cfg())

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["persisted"] is False
    assert result.data["reason_code"] == "memory_commit_writer_unavailable"
