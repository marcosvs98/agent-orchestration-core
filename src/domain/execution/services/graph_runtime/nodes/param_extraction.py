from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.graph_runtime.nodes._common import (
    #ExtractionResult,
    conversation_key_and_stateless,
    payload_from_config,
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


class ParamExtractionNode(NodeExecutor):
    node_type = NodeType.ParamExtractionNode
    llm_task = LLMTaskType.SLOT_FILLING
    side_effect = False
    deterministic = False

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        llm_executor: LLMExecutorPort | None = None,
        prompt_resolver: Any | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver
        self.tracer = tracer

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        config = config or {}
        llm_cfg = config.get("llm")


        if llm_cfg and self.llm_executor:
            runtime_policy = (
                (context.metadata or {}).get("runtime_policy", {})
                if context.metadata
                else {}
            )
            llm_policy = runtime_policy.get("llm", {})
            provider = llm_cfg.get("provider") or LLMProviderType.OPENAI.value
            model_alias = (
                llm_cfg.get("model_alias")
                or llm_policy.get("model_alias")
                or "gpt-4o-mini"
            )

            if not model_alias:
                raise DomainValidationException(message="llm_model_alias_required")
            try:
                node_uuid = UUID(context.current_node_id)
            except Exception:
                node_uuid = None

            task_type_raw = llm_cfg.get("task_type", LLMTaskType.SLOT_FILLING.value)
            try:
                task_type = LLMTaskType(task_type_raw)
            except ValueError:
                task_type = LLMTaskType.SLOT_FILLING

            with self.tracer.observe(
                as_type="chain",
                name="domain.execution.nodes.param_extraction.resolve_prompt",
                input={"node_id": str(node_uuid) if node_uuid else None},
            ):
                resolved_prompt = await self.prompt_resolver.resolve(
                    intent=PromptIntent.SLOT_FILLING,
                    context=context,
                    node_id=node_uuid,
                )
            request = LLMRequest(
                prompt=resolved_prompt.prompt_text,
                system_prompt=context.system_prompt,
                user_message=read_user_input(context),
                input_schema=resolved_prompt.input_schema
                or llm_cfg.get("input_schema", {}),
                output_schema=resolved_prompt.output_schema
                or llm_cfg.get("output_schema", {}),
                json_schema=resolved_prompt.output_schema
                or llm_cfg.get("output_schema", {}),
                json_schema_name="slot_filling_output",
                model_alias=model_alias,
                temperature=llm_cfg.get("temperature")
                if (llm_cfg and "temperature" in llm_cfg)
                else llm_policy.get("temperature"),
                max_tokens=llm_policy.get("max_tokens"),
                max_latency_ms=llm_policy.get("max_latency_ms"),
                max_cost_usd=llm_policy.get("max_cost_usd"),
                retry_limit=llm_policy.get("retry_limit"),
                fallback_model_alias=llm_policy.get("fallback_model_alias"),
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
                        context.tenant_id,
                        context.session_id,
                    )
                )[0],
                stateless=_conv_key[1],
            )
            with self.tracer.observe(
                as_type="chain",
                name="domain.execution.nodes.param_extraction.execute_llm",
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
                )
                if chain_handle:
                    chain_handle.success(output=llm_result.model_dump(mode="json"))

            next_state = {**context.state, self.node_type: llm_result.output}
            return NodeResult(
                node=self.node_type,
                status=NodeExecutionStatus.SUCCESS,
                data=llm_result.output,
                metrics=llm_result.token_usage,
                next_state=next_state,
            )

        data = payload_from_config(config) or []

        next_state = {**(context.state or {}), self.node_type: data}

        return NodeResult(
            node=self.node_type,
            status=NodeExecutionStatus.ERROR,
            data={},
            next_state=next_state
        )