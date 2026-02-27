from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
    UserContextEnrichmentMode,
)
from domain.prompts.schemas.prompt import NodeType


class UserContextEnrichmentNode(NodeExecutor):
    node_type = NodeType.UserContextEnrichmentNode
    side_effect = False
    deterministic = True

    def __init__(self, tracer: RuntimeTracerPort) -> None:
        self.tracer = tracer

    @staticmethod
    def _resolve_runtime_policy(context: ExecutionContext) -> dict[str, Any]:
        if not isinstance(context.metadata, dict):
            return {}
        runtime_policy = context.metadata.get("runtime_policy")
        if not isinstance(runtime_policy, dict):
            return {}
        user_context_policy = runtime_policy.get("user_context_enrichment")
        if not isinstance(user_context_policy, dict):
            return {}
        return user_context_policy

    @staticmethod
    def _resolve_layers(
        *,
        config: Dict[str, Any],
        runtime_policy: dict[str, Any],
    ) -> dict[str, bool]:
        candidate = config.get("layers")
        if not isinstance(candidate, dict):
            candidate = runtime_policy.get("default_layers_when_published")
        if not isinstance(candidate, dict):
            candidate = {}

        return {
            "allow_tenant_knowledge": bool(
                candidate.get("allow_tenant_knowledge", True)
            ),
            "allow_user_memory_structured": bool(
                candidate.get("allow_user_memory_structured", True)
            ),
            "allow_user_memory_vector": bool(
                candidate.get("allow_user_memory_vector", True)
            ),
        }

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        config = config or {}
        runtime_policy = self._resolve_runtime_policy(context)
        handle_state = context.get_node_output(NodeType.UserContextEnrichmentNode)
        enabled = bool(runtime_policy.get("enabled", False))
        publish = bool(config.get("publish", True))
        mode = (
            UserContextEnrichmentMode.GATED
            if bool(runtime_policy.get("gating"))
            else UserContextEnrichmentMode.LEGACY
        )
        layers = self._resolve_layers(config=config, runtime_policy=runtime_policy)
        published = bool(enabled and publish)
        published_at = datetime.now(UTC).isoformat() if published else None
        published_by_node_id = context.current_node_id if published else None
        data = {
            "enabled": enabled,
            "published": published,
            "mode": mode,
            "layers": layers,
        }
        next_state = {
            **(context.state or {}),
            self.node_type: {
                **handle_state,
                **data,
                "published_by_node_id": published_by_node_id,
                "published_at": published_at,
            },
        }

        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=data,
            next_state=next_state,
        )
