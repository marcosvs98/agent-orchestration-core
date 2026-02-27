from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from application.prompts.prompt_resolver import PromptResolver
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.services.graph_runtime.agent_runtime_resolver import (
    AgentRuntimeResolver,
)
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.graph_runtime.nodes._common import (
    conversation_key_and_stateless,
    read_user_input,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
)
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import (
    LLMProviderType,
    LLMRequest,
    LLMResult,
    LLMTaskType,
)
from domain.prompts.schemas.prompt import NodeType, PromptIntent
from exceptions.service_exceptions import DomainValidationException


class ToolSelectionNode(NodeExecutor):
    node_type = NodeType.ToolSelectionNode
    llm_task = LLMTaskType.TOOL_SELECTION
    side_effect = False
    deterministic = False

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_executor: LLMExecutorPort,
        prompt_resolver: PromptResolver,
        agent_runtime_resolver: AgentRuntimeResolver | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.tracer = tracer
        self.agent_runtime_resolver = agent_runtime_resolver

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        config = config or {}
        llm_cfg = config.get("llm")

        runtime_policy = (
            (context.metadata or {}).get("runtime_policy", {})
            if context.metadata
            else {}
        )
        llm_policy = runtime_policy.get("llm", {})
        provider = llm_cfg.get("provider") or LLMProviderType.OPENAI.value
        model_alias = llm_cfg.get("model_alias") or "gpt-4o-mini"
        try:
            node_uuid = UUID(context.current_node_id)
        except (ValueError, TypeError):
            node_uuid = None

        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.nodes.tool_selection.resolve_prompt",
            input={"node_id": str(node_uuid) if node_uuid else None},
        ) as chain_handle:
            resolved_prompt = await self.prompt_resolver.resolve(
                intent=PromptIntent.INTENT_TOOL_SELECTION,
                context=context,
                node_id=node_uuid,
                node_type=self.node_type,
            )
            if chain_handle:
                chain_handle.success(output=resolved_prompt.model_dump(mode="json"))

        if self.agent_runtime_resolver and node_uuid:
            system_prompt = await self.agent_runtime_resolver.resolve_system_prompt(
                context.flow_run_id, node_uuid, context.state
            )
        else:
            system_prompt = context.system_prompt

        llm_request = LLMRequest(
            prompt=resolved_prompt.prompt_text,
            system_prompt=system_prompt,
            user_message=read_user_input(context),
            input_schema=resolved_prompt.input_schema,
            output_schema=resolved_prompt.output_schema,
            json_schema=resolved_prompt.output_schema
            or llm_cfg.get("output_schema", {}),
            json_schema_name="tool_selection_output",
            model_alias=model_alias,
            temperature=(
                llm_cfg.get("temperature")
                if (llm_cfg and "temperature" in llm_cfg)
                else llm_policy.get("temperature")
            ),
            max_tokens=llm_policy.get("max_tokens"),
            max_latency_ms=llm_policy.get("max_latency_ms"),
            max_cost_usd=llm_policy.get("max_cost_usd"),
            retry_limit=llm_policy.get("retry_limit"),
            fallback_model_alias=llm_cfg.get("fallback_model_alias"),
            available_tools=context.available_tools,
            prompt_id=str(resolved_prompt.prompt_id)
            if resolved_prompt.prompt_id
            else None,
            prompt_version=resolved_prompt.prompt_version,
            prompt_frozen_hash=resolved_prompt.prompt_frozen_hash,
            task_type=self.llm_task,
            user_id=context.user_id,
            conversation_key=(
                _conv_key := conversation_key_and_stateless(
                    self.llm_task,
                    llm_policy,
                    str(context.tenant_id),
                    str(context.session_id),
                )
            )[0],
            stateless=_conv_key[1],
        )
        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.nodes.tool_selection.execute_llm",
            input=llm_request.model_dump(mode="json"),
        ) as chain_handle:
            llm_result: LLMResult = await self.llm_executor.execute_llm(
                request=llm_request,
                trace=TraceContext(
                    trace_id=context.trace_id or UUID(int=0),
                    flow_run_id=context.flow_run_id,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                ),
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                correlation_id=context.correlation_id,
                node_id=node_uuid,
                provider=provider,
                policy_llm=llm_policy,
            )
            if chain_handle:
                chain_handle.success(output=llm_result.model_dump(mode="json"))

        if not isinstance(llm_result.output, dict):
            raise DomainValidationException(message="invalid_intent_output_contract")

        next_state = {**(context.state or {}), self.node_type: llm_result.output}

        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.SUCCESS,
            data=llm_result.output,
            metrics=llm_result.token_usage,
            next_state=next_state,
        )
