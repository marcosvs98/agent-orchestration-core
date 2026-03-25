from __future__ import annotations

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes._common import read_user_input
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
)
from domain.llm.schemas.moderation import ModerationResult
from domain.llm.ports.moderation_provider import ModerationProviderPort
from domain.prompts.schemas.prompt import NodeType


class ContentModeration(NodeExecutor):
    node_type = NodeType.ContentModeration
    side_effect = False
    deterministic = True

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_moderation_provider: ModerationProviderPort,
    ) -> None:
        self.tracer = tracer
        self.llm_moderation_provider = llm_moderation_provider

    async def execute(
        self, context: ExecutionContext, config: dict[str, object] | None = None
    ) -> NodeResult:
        merged_config = self._resolve_config(context=context, config=config)
        user_input = read_user_input(context)
        result: ModerationResult = await self.llm_moderation_provider.moderate(
            text=user_input, config=merged_config
        )
        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data={
                "flagged": result.flagged,
                "categories": result.categories,
            },
        )

    @staticmethod
    def _resolve_config(
        *,
        context: ExecutionContext,
        config: dict[str, object] | None,
    ) -> dict[str, object]:
        resolved: dict[str, object] = {}
        metadata = context.metadata if isinstance(context.metadata, dict) else {}
        runtime_policy = metadata.get("runtime_policy")
        if isinstance(runtime_policy, dict):
            moderation_cfg = runtime_policy.get("moderation")
            if isinstance(moderation_cfg, dict):
                resolved.update(moderation_cfg)
        if config:
            resolved.update(config)
        return resolved
