from __future__ import annotations

import asyncio
from typing import Any, Dict, Final
from uuid import uuid4

from examples.support import NullTracer, build_context, expect, field, heading

from domain.execution.services.graph_runtime.nodes.tool_error_handler import ToolErrorHandlerNode
from domain.execution.services.graph_runtime.nodes.tool_executor import ToolExecutor
from domain.prompts.schemas.prompt import NodeType

TOOL_CONFIG_ID: Final[str] = str(uuid4())


class FlakyOrchestrator:
    def __init__(self, fail_first_call_for: set[str]) -> None:
        self.fail_first_call_for = set(fail_first_call_for)
        self.executed: list[str] = []
        self._tool_run_inputs: Dict[str, str] = {}

    def remember(self, tool_run_id: str, operation_id: str) -> None:
        self._tool_run_inputs[tool_run_id] = operation_id

    async def execute_tool_run(self, *, tool_run_id: Any) -> Dict[str, Any]:
        operation_id = self._tool_run_inputs[str(tool_run_id)]
        self.executed.append(operation_id)
        if operation_id in self.fail_first_call_for:
            self.fail_first_call_for.discard(operation_id)
            raise RuntimeError("upstream returned 503")
        return {"ok": True, "operation_id": operation_id}


class RecordingRepository:
    def __init__(self, orchestrator: FlakyOrchestrator) -> None:
        self.orchestrator = orchestrator
        self.created: list[str] = []

    async def create_tool_run(self, **kwargs: Any) -> Any:
        tool_run_id = uuid4()
        operation_id = str(kwargs["idempotency_key"]).rsplit(":", 1)[-1]
        self.created.append(operation_id)
        self.orchestrator.remember(str(tool_run_id), operation_id)
        return tool_run_id


def _state() -> Dict[str, Any]:
    return {
        NodeType.ToolInputFiller.value: {
            "result": [
                {
                    "operation_id": "op_charge",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 10},
                },
                {
                    "operation_id": "op_notify",
                    "tool_name": "createExpense",
                    "status": "ready",
                    "params": {"amount": 20},
                },
            ]
        },
        NodeType.ToolResolver.value: {
            "result": [
                {
                    "selected_tool": {
                        "name": "createExpense",
                        "tool_id": str(uuid4()),
                        "tool_config_id": TOOL_CONFIG_ID,
                    }
                }
            ]
        },
    }


async def main() -> None:
    print("ToolErrorHandlerNode -> ToolExecutor: retrying only what failed")

    orchestrator = FlakyOrchestrator(fail_first_call_for={"op_notify"})
    repository = RecordingRepository(orchestrator)
    executor = ToolExecutor(
        tool_orchestrator=orchestrator,
        execution_repository=repository,
        tracer=NullTracer(),
    )
    handler = ToolErrorHandlerNode()

    heading("Pass 1: both operations execute, one fails")
    first = await executor.execute(build_context(state=_state()))
    statuses = {item["operation_id"]: item["status"] for item in first.data["result"]}
    field("executed", orchestrator.executed)
    field("statuses", statuses)
    expect(len(orchestrator.executed) == 2, "both operations ran on the first pass")

    heading("Error handler classifies the failure")
    handled = await handler.execute(
        build_context(state=first.next_state or {}), config={"max_retries": 1}
    )
    field("retry_operation_ids", handled.data["retry_operation_ids"])
    field("finalized_results", [r["operation_id"] for r in handled.data["finalized_results"]])
    field("fallback_required", handled.data["fallback_required"])
    expect(
        handled.data["retry_operation_ids"] == ["op_notify"],
        "only the failed operation is queued for retry",
    )

    heading("Pass 2: the LOOP edge routes back to ToolExecutor")
    retry_state = {**_state(), **(handled.next_state or {})}
    orchestrator.executed.clear()
    second = await executor.execute(build_context(state=retry_state))
    field("executed", orchestrator.executed)
    expect(
        orchestrator.executed == ["op_notify"],
        "the already-successful operation is NOT charged a second time",
    )

    merged = {item["operation_id"]: item["status"] for item in second.data["result"]}
    field("merged result set", merged)
    expect(set(merged) == {"op_charge", "op_notify"}, "both results survive the retry pass")
    expect(merged["op_notify"] == "success", "the retried operation now succeeds")
    expect(
        (second.next_state or {})["retry_operation_ids"] == [],
        "the retry selection is cleared so the next pass is not filtered",
    )

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
