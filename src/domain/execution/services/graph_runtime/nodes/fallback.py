from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from domain.human_sla.schemas.sla_case import SLAFallbackReason
from domain.human_sla.services.human_sla_service import HumanSLAService
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType


class FallbackNode(NodeExecutor):
    node_type = NodeType.FallbackNodeSLA
    side_effect = True
    deterministic = True

    def __init__(self, human_sla_service: HumanSLAService | None = None) -> None:
        self.human_sla_service = human_sla_service

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        node_config = config or {}
        fallback_reason_raw = node_config.get(
            "fallback_reason",
            SLAFallbackReason.UNKNOWN_INTENT.value,
        )
        if fallback_reason_raw is None or fallback_reason_raw == "":
            fallback_reason_raw = SLAFallbackReason.UNKNOWN_INTENT.value
        try:
            fallback_reason = SLAFallbackReason(str(fallback_reason_raw).upper())
        except ValueError:
            fallback_reason = SLAFallbackReason.UNKNOWN_INTENT

        origin_node = context.metadata.get("origin_node") or context.state.get(
            "origin_node"
        )
        operation_ids = (
            context.metadata.get("operation_ids")
            or context.state.get("operation_ids")
            or []
        )
        interaction_id_value = context.metadata.get(
            "interaction_id"
        ) or context.state.get("interaction_id")
        interaction_id: UUID | None = None
        if interaction_id_value is not None:
            try:
                interaction_id = UUID(str(interaction_id_value))
            except ValueError:
                interaction_id = None

        sla_case_id: UUID | None = None
        if (
            self.human_sla_service is not None
            and context.current_node_run_id is not None
        ):
            sla_case_id = await self.human_sla_service.create_case_for_fallback(
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                node_run_id=context.current_node_run_id,
                interaction_id=interaction_id,
                user_id=context.user_id,
                fallback_reason=fallback_reason,
                priority=node_config.get("priority"),
                opened_at=datetime.now(timezone.utc),
            )

        data = {
            "system_output": node_config.get(
                "system_output",
                "We could not complete your request automatically. A human specialist will continue from here.",
            ),
            "severity": node_config.get("severity", "medium"),
            "fallback": {
                "reason": fallback_reason.value,
                "origin_node": origin_node,
                "operation_ids": operation_ids,
                "sla_triggered": sla_case_id is not None,
                "ticket_id": str(sla_case_id) if sla_case_id is not None else None,
            },
        }
        return NodeResult(
            node=self.node_type, status=NodeExecutionStatus.SUCCESS, data=data
        )
