from __future__ import annotations

import json
import uuid
from typing import Any, Dict

import pytest

from domain.execution.services.graph_runtime.nodes.context_summarizer import (
    ContextSummarizer,
    ContextSummarizerReason,
)
from domain.execution.services.graph_runtime.types import (
    MEMORY_CONTENT_SUMMARIZE_STAGING_KEY,
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType

SOURCE_NODE_ID = "00000000-0000-0000-0000-000000000801"


class _RecordingSummarizer(ContextSummarizer):
    def __init__(self, summary: Dict[str, Any] | None = None) -> None:
        self.seen_state: Dict[str, Any] | None = None
        self.calls = 0
        self.summary = summary if summary is not None else {"summary": "short"}

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        return await ContextSummarizer.execute(self, context, config)

    async def _run_llm_after_setup(
        self, context: ExecutionContext, config: Dict[str, Any]
    ) -> NodeResult:
        self.calls += 1
        self.seen_state = dict(context.state)
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=self.summary,
            metrics={"total_tokens": 42},
            next_state={**context.state, self.node_type.value: self.summary},
        )


def _ctx(state: Dict[str, Any] | None = None) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=uuid.uuid4(),
        interaction_id=uuid.uuid4(),
        user_id="u1",
        session_id=uuid.uuid4(),
        input_payload={"user_input": "hello"},
        flow_id=uuid.uuid4(),
        flow_version_id=uuid.uuid4(),
        flow_run_id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        current_node_id=str(uuid.uuid4()),
        state=state or {},
    )


def _large_source_output(size: int = 4096) -> Dict[str, Any]:
    return {"result": [{"params": {"blob": "x" * size}}]}


@pytest.mark.asyncio
async def test_below_threshold_skips_llm_and_leaves_state_untouched() -> None:
    node = _RecordingSummarizer()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: {"result": [{"params": {"a": 1}}]}}}
    ctx = _ctx(state)

    result = await node.execute(
        ctx,
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": 4096},
    )

    assert node.calls == 0
    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.node == NodeType.ContextSummarizer
    assert result.data["summarized"] is False
    assert result.data["reason_code"] == ContextSummarizerReason.BELOW_THRESHOLD.value
    assert result.next_state == state
    assert ContextSummarizer.node_type.value not in (result.next_state or {})


@pytest.mark.asyncio
async def test_above_threshold_stages_raw_payload_for_the_prompt() -> None:
    node = _RecordingSummarizer()
    source_output = _large_source_output()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: source_output}}

    result = await node.execute(
        _ctx(state),
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": 4096},
    )

    assert node.calls == 1
    assert node.seen_state is not None
    staged = node.seen_state[MEMORY_CONTENT_SUMMARIZE_STAGING_KEY]
    assert staged["source_node_id"] == SOURCE_NODE_ID
    assert json.loads(staged["raw"]) == source_output
    assert staged["payload_bytes"] == len(
        json.dumps(source_output, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    )
    assert result.data["summarized"] is True
    assert result.data["reason_code"] == ContextSummarizerReason.COMPACTED.value


@pytest.mark.asyncio
async def test_staging_key_is_removed_from_next_state() -> None:
    node = _RecordingSummarizer()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: _large_source_output()}}

    result = await node.execute(
        _ctx(state),
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": 1},
    )

    assert MEMORY_CONTENT_SUMMARIZE_STAGING_KEY not in (result.next_state or {})
    assert (result.next_state or {})[NodeType.ContextSummarizer.value] == {"summary": "short"}


@pytest.mark.asyncio
async def test_compaction_metrics_report_saved_bytes() -> None:
    node = _RecordingSummarizer()
    source_output = _large_source_output()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: source_output}}

    result = await node.execute(
        _ctx(state),
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": 1},
    )

    compaction = result.data["compaction"]
    assert compaction["payload_bytes"] > compaction["summary_bytes"]
    assert compaction["saved_bytes"] == compaction["payload_bytes"] - compaction["summary_bytes"]
    assert 0 < compaction["compaction_ratio"] < 1
    assert compaction["source_output_replaced"] is False
    assert result.metrics is not None
    assert result.metrics["total_tokens"] == 42
    assert result.metrics["compaction"] == compaction


@pytest.mark.asyncio
async def test_source_output_preserved_by_default() -> None:
    node = _RecordingSummarizer()
    source_output = _large_source_output()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: source_output}}

    result = await node.execute(
        _ctx(state),
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": 1},
    )

    snapshot = (result.next_state or {})[NODE_OUTPUTS_BY_NODE_ID_KEY]
    assert snapshot[SOURCE_NODE_ID] == source_output


@pytest.mark.asyncio
async def test_replace_source_output_compacts_the_snapshot() -> None:
    node = _RecordingSummarizer()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: _large_source_output()}}

    result = await node.execute(
        _ctx(state),
        config={
            "source_node_id": SOURCE_NODE_ID,
            "min_payload_bytes_to_run": 1,
            "replace_source_output": True,
        },
    )

    snapshot = (result.next_state or {})[NODE_OUTPUTS_BY_NODE_ID_KEY]
    assert snapshot[SOURCE_NODE_ID] == {"summary": "short"}
    assert result.data["compaction"]["source_output_replaced"] is True


@pytest.mark.asyncio
async def test_missing_source_output_skips_without_llm() -> None:
    node = _RecordingSummarizer()

    result = await node.execute(
        _ctx({NODE_OUTPUTS_BY_NODE_ID_KEY: {}}),
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": 1},
    )

    assert node.calls == 0
    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["reason_code"] == ContextSummarizerReason.SOURCE_OUTPUT_MISSING.value


@pytest.mark.asyncio
async def test_missing_source_node_id_is_an_error() -> None:
    node = _RecordingSummarizer()

    result = await node.execute(_ctx(), config={"min_payload_bytes_to_run": 1})

    assert node.calls == 0
    assert result.status == NodeExecutionStatus.ERROR
    assert result.data["reason_code"] == ContextSummarizerReason.SOURCE_NODE_ID_MISSING.value


@pytest.mark.asyncio
async def test_invalid_threshold_falls_back_to_default() -> None:
    node = _RecordingSummarizer()
    state = {NODE_OUTPUTS_BY_NODE_ID_KEY: {SOURCE_NODE_ID: {"a": 1}}}

    result = await node.execute(
        _ctx(state),
        config={"source_node_id": SOURCE_NODE_ID, "min_payload_bytes_to_run": "not-an-int"},
    )

    assert node.calls == 1
    assert result.data["compaction"]["min_payload_bytes_to_run"] == 1
