from __future__ import annotations

from typing import Any, Dict

from domain.human_sla.schemas.sla_case import SLAFallbackReason
from domain.prompts.schemas.prompt import NodeType

DEFAULT_FALLBACK_REASON = SLAFallbackReason.LOW_CONFIDENCE


def _has_intent(node_output: Dict[str, Any]) -> bool:
    result = node_output.get("result")
    if not isinstance(result, list) or not result:
        return False
    first = result[0]
    if not isinstance(first, dict):
        return False
    intent = first.get("intent_type")
    return isinstance(intent, str) and bool(intent.strip())


def resolve_fallback_reason(
    *,
    source_node_type: str | None,
    node_output: Dict[str, Any] | None,
) -> SLAFallbackReason:
    output = node_output if isinstance(node_output, dict) else {}

    if source_node_type == NodeType.ContentModeration.value:
        return SLAFallbackReason.POLICY_BLOCK

    if source_node_type == NodeType.ToolErrorHandlerNode.value:
        return SLAFallbackReason.TOOL_FAILURE

    if source_node_type == NodeType.ToolExecutor.value:
        return SLAFallbackReason.TOOL_FAILURE

    if source_node_type == NodeType.IntentClassifier.value:
        if not _has_intent(output):
            return SLAFallbackReason.UNKNOWN_INTENT
        return SLAFallbackReason.LOW_CONFIDENCE

    return DEFAULT_FALLBACK_REASON
