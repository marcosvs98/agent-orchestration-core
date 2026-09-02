from __future__ import annotations

import json
from enum import StrEnum
from typing import Any, Dict

from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import (
    MEMORY_CONTENT_SUMMARIZE_STAGING_KEY,
    NODE_OUTPUTS_BY_NODE_ID_KEY,
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent

DEFAULT_MIN_PAYLOAD_BYTES_TO_RUN = 1


class ContextSummarizerReason(StrEnum):
    COMPACTED = "context_summarizer_compacted"
    BELOW_THRESHOLD = "context_summarizer_below_threshold"
    SOURCE_OUTPUT_MISSING = "context_summarizer_source_output_missing"
    SOURCE_NODE_ID_MISSING = "context_summarizer_source_node_id_missing"


def _serialize_payload(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _payload_bytes(payload: Any) -> int:
    return len(_serialize_payload(payload).encode("utf-8"))


def _resolve_threshold(raw: Any) -> int:
    if raw is None:
        return DEFAULT_MIN_PAYLOAD_BYTES_TO_RUN
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_MIN_PAYLOAD_BYTES_TO_RUN


class ContextSummarizer(LLMNodeExecutor):
    node_type = NodeType.ContextSummarizer
    llm_task = LLMTaskType.MEMORY_CONTENT_SUMMARIZE
    prompt_intent = PromptIntent.MEMORY_CONTENT_SUMMARIZE
    resolve_prompt_passes_node_type = True
    include_available_tools = False
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = True
    state_key_use_value = True

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        cfg = config or {}
        source_node_id = cfg.get("source_node_id")
        threshold = _resolve_threshold(cfg.get("min_payload_bytes_to_run"))

        if not isinstance(source_node_id, str) or not source_node_id.strip():
            return NodeResult(
                node=self.node_type,
                status=NodeExecutionStatus.ERROR,
                data={
                    "summarized": False,
                    "reason_code": ContextSummarizerReason.SOURCE_NODE_ID_MISSING.value,
                    "error": ContextSummarizerReason.SOURCE_NODE_ID_MISSING.value,
                },
                next_state=context.state,
            )

        snapshot = context.state.get(NODE_OUTPUTS_BY_NODE_ID_KEY)
        source_output = snapshot.get(source_node_id) if isinstance(snapshot, dict) else None

        if source_output is None:
            return self._skipped(
                context=context,
                reason=ContextSummarizerReason.SOURCE_OUTPUT_MISSING,
                source_node_id=source_node_id,
                payload_bytes=0,
                threshold=threshold,
            )

        raw = _serialize_payload(source_output)
        payload_bytes = len(raw.encode("utf-8"))

        if payload_bytes < threshold:
            return self._skipped(
                context=context,
                reason=ContextSummarizerReason.BELOW_THRESHOLD,
                source_node_id=source_node_id,
                payload_bytes=payload_bytes,
                threshold=threshold,
            )

        staged_state = {
            **(context.state or {}),
            MEMORY_CONTENT_SUMMARIZE_STAGING_KEY: {
                "raw": raw,
                "source_node_id": source_node_id,
                "payload_bytes": payload_bytes,
            },
        }
        staged_context = context.model_copy(update={"state": staged_state})

        result = await super().execute(staged_context, cfg)

        next_state = dict(result.next_state or staged_state)
        next_state.pop(MEMORY_CONTENT_SUMMARIZE_STAGING_KEY, None)

        summary_bytes = _payload_bytes(result.data)

        if bool(cfg.get("replace_source_output", False)):
            replaced = dict(next_state.get(NODE_OUTPUTS_BY_NODE_ID_KEY) or {})
            replaced[source_node_id] = result.data
            next_state[NODE_OUTPUTS_BY_NODE_ID_KEY] = replaced

        compaction = self._compaction_stats(
            source_node_id=source_node_id,
            payload_bytes=payload_bytes,
            summary_bytes=summary_bytes,
            threshold=threshold,
            replaced=bool(cfg.get("replace_source_output", False)),
        )

        return NodeResult(
            node=self.node_type,
            status=result.status,
            data={
                **result.data,
                "summarized": True,
                "reason_code": ContextSummarizerReason.COMPACTED.value,
                "compaction": compaction,
            },
            error=result.error,
            metrics={**(result.metrics or {}), "compaction": compaction},
            next_state=next_state,
        )

    def _skipped(
        self,
        *,
        context: ExecutionContext,
        reason: ContextSummarizerReason,
        source_node_id: str,
        payload_bytes: int,
        threshold: int,
    ) -> NodeResult:
        compaction = self._compaction_stats(
            source_node_id=source_node_id,
            payload_bytes=payload_bytes,
            summary_bytes=payload_bytes,
            threshold=threshold,
            replaced=False,
        )
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data={
                "summarized": False,
                "reason_code": reason.value,
                "compaction": compaction,
            },
            metrics={"compaction": compaction},
            next_state=context.state,
        )

    @staticmethod
    def _compaction_stats(
        *,
        source_node_id: str,
        payload_bytes: int,
        summary_bytes: int,
        threshold: int,
        replaced: bool,
    ) -> Dict[str, Any]:
        saved_bytes = payload_bytes - summary_bytes
        ratio = round(summary_bytes / payload_bytes, 4) if payload_bytes > 0 else None
        return {
            "source_node_id": source_node_id,
            "payload_bytes": payload_bytes,
            "summary_bytes": summary_bytes,
            "saved_bytes": saved_bytes,
            "compaction_ratio": ratio,
            "min_payload_bytes_to_run": threshold,
            "source_output_replaced": replaced,
        }
