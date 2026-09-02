from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from examples.support import build_context, expect, field, heading

from domain.execution.services.graph_runtime.nodes.memory_commit import MemoryCommitNode
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from exceptions.service_exceptions import BaseServiceException


class NodeDefinition:
    def __init__(self, allow_memory_write: bool) -> None:
        self.allow_memory_write = allow_memory_write


class Repository:
    def __init__(self, node: NodeDefinition | None) -> None:
        self.node = node

    async def get_node(self, node_id: Any) -> NodeDefinition | None:
        return self.node


class MemoryWriter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.writes = 0

    async def write_memory_item(self, **kwargs: Any) -> None:
        self.writes += 1
        if self.error is not None:
            raise self.error
        return None


def _config() -> dict[str, Any]:
    return {
        "schema_id": "user.preference.v1",
        "schema_version": 1,
        "source": "explicit_user",
        "rag_config_id": str(uuid4()),
        "data": {"preference_key": "reporting.currency", "preference_value": "EUR"},
    }


async def _run(node: MemoryCommitNode) -> Any:
    return await node.execute(build_context(), _config())


async def main() -> None:
    print("MemoryCommitNode: the node reports what actually happened")

    heading("1. Durable write succeeds")
    writer = MemoryWriter()
    result = await _run(
        MemoryCommitNode(
            memory_write_service=writer,
            execution_repository=Repository(NodeDefinition(allow_memory_write=True)),
        )
    )
    field("status", result.status)
    field("persisted", result.data["persisted"])
    field("reason_code", result.data["reason_code"])
    expect(writer.writes == 1, "the memory item reached the writer")
    expect(result.data["persisted"] is True, "the node claims persistence only when it happened")

    heading("2. Node is not allowed to write memory")
    writer = MemoryWriter()
    result = await _run(
        MemoryCommitNode(
            memory_write_service=writer,
            execution_repository=Repository(NodeDefinition(allow_memory_write=False)),
        )
    )
    field("status", result.status)
    field("persisted", result.data["persisted"])
    field("reason_code", result.data["reason_code"])
    expect(writer.writes == 0, "no write is attempted when the node forbids it")
    expect(result.status == NodeExecutionStatus.SUCCESS, "a deliberate skip is not a failure")

    heading("3. Durable write fails")
    writer = MemoryWriter(error=BaseServiceException(message="memory_quota_exceeded"))
    result = await _run(
        MemoryCommitNode(
            memory_write_service=writer,
            execution_repository=Repository(NodeDefinition(allow_memory_write=True)),
        )
    )
    field("status", result.status)
    field("persisted", result.data["persisted"])
    field("reason_code", result.data["reason_code"])
    field("detail", result.data["detail"])
    expect(
        result.status == NodeExecutionStatus.ERROR,
        "a failed write surfaces as ERROR instead of a silent SUCCESS",
    )

    heading("4. Writer not wired (degraded deployment)")
    result = await _run(MemoryCommitNode())
    field("status", result.status)
    field("persisted", result.data["persisted"])
    field("reason_code", result.data["reason_code"])
    expect(
        result.data["reason_code"] == "memory_commit_writer_unavailable",
        "a missing collaborator is reported rather than hidden",
    )

    heading("Session memory")
    field("memory entries returned", len(result.memory or []))
    print("  note: session memory (NodeResult.memory) is always advanced;")
    print("        'persisted' refers to the durable store only.")

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
