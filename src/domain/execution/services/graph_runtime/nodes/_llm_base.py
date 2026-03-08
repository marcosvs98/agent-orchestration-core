from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.graph_runtime.agent_runtime_resolver import (
    AgentRuntimeResolver,
)
from domain.execution.services.graph_runtime.nodes._common import (
    conversation_key_and_stateless,
    read_user_input,
)
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeResult,
)
from domain.llm.ports.completion_budget_policy import CompletionBudgetPolicyPort
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import (
    LLMProviderType,
    LLMRequest,
    LLMResult,
    LLMTaskType,
)
from domain.prompts.schemas.prompt import NodeType, PromptIntent
from exceptions.service_exceptions import DomainValidationException


class LLMNodeExecutor:
    node_type: NodeType
    llm_task: LLMTaskType
    prompt_intent: PromptIntent
    side_effect = False
    deterministic = False

    resolve_prompt_passes_node_type: bool = True
    json_schema_name: str = ""
    include_available_tools: bool = False
    result_status: NodeExecutionStatus = NodeExecutionStatus.SUCCESS
    write_next_state: bool = True
    state_key_use_value: bool = False

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_executor: LLMExecutorPort,
        prompt_resolver: Any,
        agent_runtime_resolver: AgentRuntimeResolver | None = None,
        completion_budget_policy: CompletionBudgetPolicyPort | None = None,
    ) -> None:
        self.tracer = tracer
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.agent_runtime_resolver = agent_runtime_resolver
        self.completion_budget_policy = completion_budget_policy

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
        stream_enabled = bool(llm_policy.get("stream_enabled", False))
        raw_stream_eligible_tasks = llm_policy.get("stream_eligible_tasks", [])
        stream_eligible_tasks = (
            [task for task in raw_stream_eligible_tasks if isinstance(task, str)]
            if isinstance(raw_stream_eligible_tasks, list)
            else []
        )
        on_delta = context.on_content_delta
        should_stream = (
            stream_enabled
            and on_delta is not None
            and (
                not stream_eligible_tasks
                or self.llm_task.value in stream_eligible_tasks
            )
        )
        provider = llm_cfg.get("provider") or LLMProviderType.OPENAI.value
        model_alias = llm_cfg.get("model_alias") or llm_policy.get("model_alias")
        if not model_alias:
            raise DomainValidationException(message="llm_model_alias_required")
        try:
            node_uuid = UUID(context.current_node_id)
        except (ValueError, TypeError, Exception):
            node_uuid = None
        resolve_kw: Dict[str, Any] = {
            "intent": self.prompt_intent,
            "context": context,
            "node_id": node_uuid,
        }
        if self.resolve_prompt_passes_node_type:
            resolve_kw["node_type"] = self.node_type
        _trace_prefix = self.__class__.__name__.lower()
        with self.tracer.observe(
            as_type="chain",
            name=f"domain.execution.nodes.{_trace_prefix}.resolve_prompt",
            input={"node_id": str(node_uuid) if node_uuid else None},
        ) as chain_handle:
            resolved_prompt = await self.prompt_resolver.resolve(**resolve_kw)
            if chain_handle:
                chain_handle.success(output=resolved_prompt.model_dump(mode="json"))
        if self.agent_runtime_resolver and node_uuid:
            system_prompt = await self.agent_runtime_resolver.resolve_system_prompt(
                context.flow_run_id, node_uuid, context.state
            )
        else:
            system_prompt = context.system_prompt
        if not (llm_cfg or {}).get("use_system_prompt", True):
            system_prompt = None
        system_context = context.system_context
        if not (llm_cfg or {}).get("use_system_context", True):
            system_context = None
        input_schema = resolved_prompt.input_schema or llm_cfg.get("input_schema", {})
        output_schema = resolved_prompt.output_schema or llm_cfg.get(
            "output_schema", {}
        )
        json_schema = output_schema or llm_cfg.get("output_schema", {})
        user_message = read_user_input(context)
        ceiling = (
            llm_cfg.get("max_tokens")
            if llm_cfg and llm_cfg.get("max_tokens") is not None
            else llm_policy.get("max_tokens")
        )
        if self.completion_budget_policy and output_schema:
            max_tokens = self.completion_budget_policy.compute_max_tokens(
                provider_model=model_alias,
                user_message=user_message,
                output_schema=output_schema,
                policy_max=ceiling,
                completion_budget=llm_cfg.get("completion_budget") if llm_cfg else None,
            )
        else:
            max_tokens = ceiling
        request = LLMRequest(
            prompt=resolved_prompt.prompt_text,
            system_prompt=system_prompt,
            system_context=system_context,
            user_message=user_message,
            input_schema=input_schema,
            output_schema=output_schema,
            json_schema=json_schema,
            json_schema_name=self.json_schema_name
            or (self.__class__.__name__.lower() + "_output"),
            model_alias=model_alias,
            temperature=llm_cfg.get("temperature")
            if (llm_cfg and "temperature" in llm_cfg)
            else llm_policy.get("temperature"),
            max_tokens=max_tokens,
            max_latency_ms=llm_policy.get("max_latency_ms"),
            max_cost_usd=llm_policy.get("max_cost_usd"),
            retry_limit=llm_policy.get("retry_limit"),
            fallback_model_alias=llm_cfg.get("fallback_model_alias")
            or llm_policy.get("fallback_model_alias"),
            available_tools=context.available_tools
            if self.include_available_tools
            else [],
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
                    use_history_override=(
                        llm_cfg.get("use_conversation_history")
                        if llm_cfg and "use_conversation_history" in llm_cfg
                        else None
                    ),
                )
            )[0],
            stateless=_conv_key[1],
            stream=should_stream,
        )
        with self.tracer.observe(
            as_type="chain",
            name=f"domain.execution.nodes.{_trace_prefix}.execute_llm",
            input=request.model_dump(mode="json"),
        ) as chain_handle:
            llm_result: LLMResult = await self.llm_executor.execute_llm(
                request=request,
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
                on_delta=on_delta if should_stream else None,
            )
            if chain_handle:
                chain_handle.success(output=llm_result.model_dump(mode="json"))
        next_state = None
        if self.write_next_state:
            key = self.node_type.value if self.state_key_use_value else self.node_type
            next_state = {**(context.state or {}), key: llm_result.output}
        return NodeResult(
            node=self.node_type,
            status=self.result_status,
            data=llm_result.output,
            metrics=llm_result.token_usage,
            next_state=next_state,
        )
