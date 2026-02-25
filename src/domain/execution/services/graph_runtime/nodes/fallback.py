from __future__ import annotations

from typing import Any, Dict

from domain.execution.services.graph_runtime.nodes._common import payload_from_config
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
)
from domain.prompts.schemas.prompt import NodeType


class FallbackNode(NodeExecutor):
    node_type = NodeType.FallbackNodeSLA
    side_effect = False
    deterministic = True

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        data = payload_from_config(
            config, {"reason": "fallback", "message": "fallback"}
        )
        return NodeResult(node=self.node_type, status=NodeExecutionStatus.SUCCESS, data=data)
