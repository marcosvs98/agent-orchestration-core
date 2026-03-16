from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.nodes._llm_base import LLMNodeExecutor
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.human_sla.schemas.sla_case import SLAFallbackReason, SeverityLevel
from domain.human_sla.services.human_sla_service import HumanSLAService
from domain.llm.ports.completion_budget_policy import CompletionBudgetPolicyPort
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent
from domain.execution.services.graph_runtime.agent_runtime_resolver import (
    AgentRuntimeResolver,
)


class FallbackNode(LLMNodeExecutor):
    node_type = NodeType.FallbackNodeSLA
    llm_task = LLMTaskType.FALLBACK_RESPONSE
    prompt_intent = PromptIntent.FALLBACK_RESPONSE
    side_effect = True
    deterministic = True
    resolve_prompt_passes_node_type = True
    include_available_tools = False
    result_status = NodeExecutionStatus.SUCCESS
    write_next_state = False
    state_key_use_value = False

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_executor: LLMExecutorPort,
        prompt_resolver: Any,
        human_sla_service: HumanSLAService | None = None,
        agent_runtime_resolver: AgentRuntimeResolver | None = None,
        completion_budget_policy: CompletionBudgetPolicyPort | None = None,
    ) -> None:
        super().__init__(
            tracer=tracer,
            llm_executor=llm_executor,
            prompt_resolver=prompt_resolver,
            agent_runtime_resolver=agent_runtime_resolver,
            completion_budget_policy=completion_budget_policy,
        )
        self.human_sla_service = human_sla_service

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        if (
            self.human_sla_service is not None
            and context.current_node_run_id is not None
        ):
            (
                await self.human_sla_service.get_or_create_open_case_for_fallback(
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    flow_run_id=context.flow_run_id,
                    node_run_id=context.current_node_run_id,
                    interaction_id=context.interaction_id,
                    user_id=context.user_id,
                    fallback_reason=SLAFallbackReason.LOW_CONFIDENCE,
                    priority=SeverityLevel.LOW,
                    opened_at=datetime.now(timezone.utc),
                    # sla_target_at=
                )
            )

        return await super().execute(context)
