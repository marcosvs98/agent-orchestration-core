from __future__ import annotations

from typing import Any, Dict

from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
    OperationStatus,
)
from domain.prompts.schemas.prompt import NodeType


class ToolErrorHandlerNode(NodeExecutor):
    node_type = NodeType.ToolErrorHandlerNode
    side_effect = False
    deterministic = True

    def __init__(self) -> None:
        pass

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        config = config or {}
        current_state = context.state or {}
        tool_out = context.get_node_output(NodeType.ToolExecutionNode)
        results = tool_out.get("result")
        if not isinstance(results, list) and isinstance(context.node_output, dict):
            results = context.node_output.get("result")
        if not isinstance(results, list):
            legacy_results = tool_out.get("results")
            if isinstance(legacy_results, list):
                results = legacy_results
        if not isinstance(results, list) and isinstance(context.node_output, dict):
            legacy_node_output_results = context.node_output.get("results")
            if isinstance(legacy_node_output_results, list):
                results = legacy_node_output_results
        if not isinstance(results, list):
            results = []
        max_retries_raw = config.get("max_retries", 0)
        try:
            max_retries = max(0, int(max_retries_raw))
        except (TypeError, ValueError):
            max_retries = 0
        retry_counts = current_state.get("retry_counts")
        if not isinstance(retry_counts, dict):
            retry_counts = {}
        normalized_retry_counts: dict[str, int] = {}
        for key, value in retry_counts.items():
            if not isinstance(key, str):
                continue
            try:
                normalized_retry_counts[key] = int(value)
            except (TypeError, ValueError):
                continue
        retry_counts = normalized_retry_counts
        retry_operation_ids: list[str] = []
        finalized_results: list[dict[str, object]] = []
        fallback_required = False
        for result in results:
            if not isinstance(result, dict):
                continue
            operation_id = result.get("operation_id")
            status = result.get("status")
            if not isinstance(operation_id, str):
                continue
            is_retry_eligible_status = status in {
                OperationStatus.ERROR,
                OperationStatus.INCOMPLETE,
                OperationStatus.CANCELLED,
                OperationStatus.ERROR.value,
                OperationStatus.INCOMPLETE.value,
                OperationStatus.CANCELLED.value,
            }
            if is_retry_eligible_status:
                attempts = int(retry_counts.get(operation_id, 0))
                if attempts < max_retries:
                    retry_operation_ids.append(operation_id)
                    retry_counts[operation_id] = attempts + 1
                else:
                    fallback_required = True
                    finalized_results.append(result)
            else:
                finalized_results.append(result)
        payload = {
            "retry_operation_ids": retry_operation_ids,
            "retry_operation_ids_count": len(retry_operation_ids),
            "finalized_results": finalized_results,
            "finalized_results_count": len(finalized_results),
            "fallback_required": fallback_required,
        }
        next_state = {
            **current_state,
            "retry_counts": retry_counts,
            "finalized_results": finalized_results,
        }
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=payload,
            next_state=next_state,
        )
