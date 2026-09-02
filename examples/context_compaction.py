from __future__ import annotations

import asyncio
from typing import Any, Dict, Final

from examples.support import build_context, expect, field, heading

from domain.execution.services.graph_runtime.nodes.context_summarizer import ContextSummarizer
from domain.execution.services.graph_runtime.types import (
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)

SOURCE_NODE_ID: Final[str] = "00000000-0000-0000-0000-000000000801"
THRESHOLD_BYTES: Final[int] = 4096


class StubSummarizer(ContextSummarizer):
    def __init__(self) -> None:
        self.llm_calls = 0

    async def _run_llm_after_setup(
        self, context: ExecutionContext, config: Dict[str, Any]
    ) -> NodeResult:
        self.llm_calls += 1
        summary = {"summary": "user wants a monthly spend report for the last quarter"}
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=summary,
            metrics={"total_tokens": 128},
            next_state={**context.state, self.node_type.value: summary},
        )


def _state(payload_size: int) -> Dict[str, Any]:
    bulky = {
        "result": [
            {
                "operation_id": "op_1",
                "params": {"transactions": [{"id": index} for index in range(payload_size)]},
            }
        ]
    }
    return {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: bulky}}


def _config(replace: bool = False) -> Dict[str, Any]:
    return {
        "source_node_id": SOURCE_NODE_ID,
        "min_payload_bytes_to_run": THRESHOLD_BYTES,
        "replace_source_output": replace,
    }


async def main() -> None:
    print("ContextSummarizer: size-gated context compaction")
    print(f"threshold = {THRESHOLD_BYTES} bytes")

    heading("1. Small payload stays untouched")
    node = StubSummarizer()
    small = _state(payload_size=5)
    result = await node.execute(build_context(state=small), _config())
    field("reason_code", result.data["reason_code"])
    field("payload_bytes", result.data["compaction"]["payload_bytes"])
    field("llm calls", node.llm_calls)
    expect(node.llm_calls == 0, "no LLM call below the threshold")
    expect(result.next_state == small, "graph state is unchanged")

    heading("2. Large payload is compacted")
    node = StubSummarizer()
    large = _state(payload_size=400)
    result = await node.execute(build_context(state=large), _config())
    compaction = result.data["compaction"]
    field("reason_code", result.data["reason_code"])
    field("payload_bytes", compaction["payload_bytes"])
    field("summary_bytes", compaction["summary_bytes"])
    field("saved_bytes", compaction["saved_bytes"])
    field("compaction_ratio", compaction["compaction_ratio"])
    expect(node.llm_calls == 1, "the LLM ran once above the threshold")
    expect(compaction["saved_bytes"] > 0, "the summary is smaller than the source payload")

    heading("3. Source payload is preserved by default")
    snapshot = (result.next_state or {})[NODE_OUTPUTS_BY_NODE_ID_KEY]
    field("source slice still raw", "yes" if "result" in snapshot[SOURCE_NODE_ID] else "no")
    expect(
        snapshot[SOURCE_NODE_ID] == large[NODE_OUTPUTS_BY_NODE_ID_KEY][SOURCE_NODE_ID],
        "downstream nodes can still read the untouched source output",
    )

    heading("4. replace_source_output actually drops the payload")
    node = StubSummarizer()
    result = await node.execute(build_context(state=_state(400)), _config(replace=True))
    snapshot = (result.next_state or {})[NODE_OUTPUTS_BY_NODE_ID_KEY]
    field("source slice now", snapshot[SOURCE_NODE_ID])
    expect(
        "result" not in snapshot[SOURCE_NODE_ID],
        "the bulky payload no longer travels with graph state",
    )

    print()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
