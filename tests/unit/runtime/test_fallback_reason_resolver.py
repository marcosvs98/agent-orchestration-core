from __future__ import annotations

import pytest

from domain.execution.services.graph_runtime.fallback_reason_resolver import (
    resolve_fallback_reason,
)
from domain.human_sla.schemas.sla_case import SLAFallbackReason
from domain.prompts.schemas.prompt import NodeType


@pytest.mark.parametrize(
    ("node_type", "node_output", "expected"),
    [
        (
            NodeType.ContentModeration.value,
            {"flagged": True},
            SLAFallbackReason.POLICY_BLOCK,
        ),
        (
            NodeType.ToolErrorHandlerNode.value,
            {"fallback_required": True},
            SLAFallbackReason.TOOL_FAILURE,
        ),
        (
            NodeType.ToolExecutor.value,
            {"result": [{"status": "error"}]},
            SLAFallbackReason.TOOL_FAILURE,
        ),
        (
            NodeType.IntentClassifier.value,
            {"result": []},
            SLAFallbackReason.UNKNOWN_INTENT,
        ),
        (
            NodeType.IntentClassifier.value,
            {"result": [{"intent_type": "command"}]},
            SLAFallbackReason.LOW_CONFIDENCE,
        ),
        (
            NodeType.ResponseBuilder.value,
            {},
            SLAFallbackReason.LOW_CONFIDENCE,
        ),
        (None, None, SLAFallbackReason.LOW_CONFIDENCE),
    ],
)
def test_resolve_fallback_reason(node_type, node_output, expected) -> None:
    assert resolve_fallback_reason(source_node_type=node_type, node_output=node_output) == expected


def test_blank_intent_is_treated_as_unknown() -> None:
    reason = resolve_fallback_reason(
        source_node_type=NodeType.IntentClassifier.value,
        node_output={"result": [{"intent_type": "   "}]},
    )
    assert reason == SLAFallbackReason.UNKNOWN_INTENT


def test_non_dict_node_output_is_tolerated() -> None:
    reason = resolve_fallback_reason(
        source_node_type=NodeType.IntentClassifier.value,
        node_output="not-a-dict",
    )
    assert reason == SLAFallbackReason.UNKNOWN_INTENT
