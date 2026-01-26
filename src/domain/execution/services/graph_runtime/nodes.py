from __future__ import annotations

import json
from typing import Any, Dict
from uuid import UUID

from domain.agents.schemas.agents import PersonaConfig
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
    NodeExecutor,
    NodeResult,
)
from domain.execution.schemas.trace import TraceContext
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import LLMRequest, LLMResult, LLMTaskType
from domain.prompts.schemas.prompt import NodeType, PromptIntent
from exceptions.service_exceptions import DomainValidationException


def _payload_from_config(
    config: Dict[str, Any] | None, default: Dict[str, Any]
) -> Dict[str, Any]:
    if config is None:
        return default
    return config.get("output", default) or default


class IntentToolSelectionNode(NodeExecutor):
    node_type = NodeType.IntentToolSelectionNode
    side_effect = False
    deterministic = False

    def __init__(
        self,
        llm_executor: LLMExecutorPort | None = None,
        prompt_resolver: Any | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Select intent deterministically or via LLM executor when configured."""
        config = config or {}
        llm_cfg = config.get("llm")

        if llm_cfg and self.llm_executor:
            if not self.prompt_resolver:
                raise DomainValidationException(
                    message="prompt_resolver_required",
                    detail="PromptResolver is required for LLM execution",
                )

            runtime_policy = (
                (context.metadata or {}).get("runtime_policy", {})
                if context.metadata
                else {}
            )
            llm_policy = runtime_policy.get("llm", {})
            provider = llm_cfg.get("provider") or "OPENAI"
            model_alias = llm_policy.get("model_alias") or llm_cfg.get("model_alias")

            if not model_alias:
                raise DomainValidationException(message="llm_model_alias_required")

            try:
                node_uuid: UUID | None = UUID(context.current_node_id)
            except Exception:  # noqa: BLE001
                node_uuid = None

            resolved_prompt = await self.prompt_resolver.resolve(
                intent=PromptIntent.INTENT_TOOL_SELECTION,
                context=context,
                node_id=node_uuid,
            )

            task_type = LLMTaskType.INTENT_SELECTION

            request = LLMRequest(
                prompt=resolved_prompt.prompt_text,
                system_prompt=context.system_prompt,
                input_schema=resolved_prompt.input_schema or llm_cfg.get("input_schema", {}),
                output_schema=resolved_prompt.output_schema or llm_cfg.get("output_schema", {}),
                model_alias=model_alias,
                max_tokens=llm_policy.get("max_tokens"),
                max_latency_ms=llm_policy.get("max_latency_ms"),
                max_cost_usd=llm_policy.get("max_cost_usd"),
                retry_limit=llm_policy.get("retry_limit"),
                fallback_model_alias=llm_policy.get("fallback_model_alias"),
                available_tools=context.available_tools,
                prompt_version=resolved_prompt.prompt_version,
                prompt_frozen_hash=resolved_prompt.prompt_frozen_hash,
                task_type=task_type,
            )
            result: LLMResult = await self.llm_executor.execute_llm(
                request=request,
                trace=TraceContext(
                    trace_id=context.trace_id or UUID(int=0),
                    flow_run_id=context.flow_run_id,
                    tenant_id=context.tenant_id,
                ),
                tenant_id=context.tenant_id,
                session_id=context.session_id,
                flow_run_id=context.flow_run_id,
                correlation_id=context.correlation_id,
                node_id=node_uuid,
                provider=provider,
                policy_llm=llm_policy,
            )
            output_payload = result.output or {}

            tool_config_id = output_payload.get("tool_config_id")
            is_valid_uuid = False
            if tool_config_id:
                try:
                    UUID(str(tool_config_id))
                    is_valid_uuid = True
                except (ValueError, TypeError):
                    pass

            if not is_valid_uuid:
                default_tool_config_id = config.get("default_tool_config_id")
                if default_tool_config_id:
                    output_payload["tool_config_id"] = str(default_tool_config_id)

            next_state = {"intent_output": output_payload}
            return NodeResult(
                status=NodeExecutionStatus.SUCCESS,
                payload=output_payload,
                metrics=result.token_usage,
                next_state=next_state,
            )

        payload = _payload_from_config(
            config, {"validation_status": "VALID", "confidence": 1.0}
        )
        next_state = {"intent_output": payload}

        return NodeResult(
            status=NodeExecutionStatus.SUCCESS, payload=payload, next_state=next_state
        )


class ParamExtractionNode(NodeExecutor):
    node_type = NodeType.ParamExtractionNode
    side_effect = False
    deterministic = False

    def __init__(
        self,
        llm_executor: LLMExecutorPort | None = None,
        prompt_resolver: Any | None = None,
    ) -> None:
        self.llm_executor = llm_executor
        self.prompt_resolver = prompt_resolver

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Extract parameters from user input via LLM executor when configured."""

        config = config or {}
        llm_cfg = config.get("llm")

        if llm_cfg and self.llm_executor:
            if not self.prompt_resolver:
                raise DomainValidationException(
                    message="prompt_resolver_required",
                    detail="PromptResolver is required for LLM execution",
                )

            runtime_policy = (
                (context.metadata or {}).get("runtime_policy", {})
                if context.metadata
                else {}
            )
            llm_policy = runtime_policy.get("llm", {})
            provider = llm_cfg.get("provider") or "OPENAI"
            model_alias = llm_policy.get("model_alias") or llm_cfg.get("model_alias")

            if not model_alias:
                raise DomainValidationException(message="llm_model_alias_required")

            try:
                node_uuid: UUID | None = UUID(context.current_node_id)
            except Exception:  # noqa: BLE001
                node_uuid = None

            task_type_raw = llm_cfg.get("task_type", "SLOT_FILLING")
            try:
                task_type = LLMTaskType(task_type_raw)
            except ValueError:
                task_type = LLMTaskType.SLOT_FILLING

            intent = (
                PromptIntent.SLOT_FILLING
                if task_type == LLMTaskType.SLOT_FILLING
                else PromptIntent.PARAM_EXTRACTION
            )

            resolved_prompt = await self.prompt_resolver.resolve(
                intent=intent,
                context=context,
                node_id=node_uuid,
            )

            request = LLMRequest(
                prompt=resolved_prompt.prompt_text,
                system_prompt=context.system_prompt,
                input_schema=resolved_prompt.input_schema or llm_cfg.get("input_schema", {}),
                output_schema=resolved_prompt.output_schema or llm_cfg.get("output_schema", {}),
                model_alias=model_alias,
                max_tokens=llm_policy.get("max_tokens"),
                max_latency_ms=llm_policy.get("max_latency_ms"),
                max_cost_usd=llm_policy.get("max_cost_usd"),
                retry_limit=llm_policy.get("retry_limit"),
                fallback_model_alias=llm_policy.get("fallback_model_alias"),
                prompt_version=resolved_prompt.prompt_version,
                prompt_frozen_hash=resolved_prompt.prompt_frozen_hash,
                task_type=task_type,
            )

            try:
                result = await self.llm_executor.execute_llm(
                    request=request,
                    trace=TraceContext(
                        trace_id=context.trace_id or UUID(int=0),
                        flow_run_id=context.flow_run_id,
                        tenant_id=context.tenant_id,
                    ),
                    tenant_id=context.tenant_id,
                    session_id=context.session_id,
                    flow_run_id=context.flow_run_id,
                    correlation_id=context.correlation_id,
                    node_id=node_uuid,
                    provider=provider,
                    policy_llm=llm_policy,
                )

            except Exception as exc:
                raise exc from exc  # Todo: Rever isso P0

            extracted_params = result.output or {}
            current_state = context.state or {}
            next_state = {
                **current_state,
                "extracted_params": extracted_params,
                "intent_output": current_state.get("intent_output", {}),
            }

            return NodeResult(
                status=NodeExecutionStatus.SUCCESS,
                payload=result.output,
                metrics=result.token_usage,
                next_state=next_state,
            )

        payload = _payload_from_config(
            config, {"extracted_params": {}, "validation_status": "VALID"}
        )
        current_state = context.state or {}
        next_state = {
            **current_state,
            "extracted_params": payload.get("extracted_params", {}),
            "intent_output": current_state.get("intent_output", {}),
        }

        return NodeResult(
            status=NodeExecutionStatus.SUCCESS, payload=payload, next_state=next_state
        )


class ToolExecutionNode(NodeExecutor):
    node_type = NodeType.ToolExecutionNode
    side_effect = True
    deterministic = False

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Execute tool using tool_config_id and extracted parameters."""

        config = config or {}

        current_state = context.state or {}
        intent_output = current_state.get("intent_output") or {}
        extracted_params = current_state.get("extracted_params") or {}
        tool_config_id = None

        if isinstance(intent_output, dict):
            tool_config_id = intent_output.get("tool_config_id")
        elif isinstance(intent_output, str):
            try:
                intent_data = json.loads(intent_output)
                tool_config_id = intent_data.get("tool_config_id")
            except Exception:
                pass

        if not tool_config_id and context.node_output:
            tool_config_id = context.node_output.get("tool_config_id")
            if not tool_config_id:
                content_str = context.node_output.get("content", "")
                if isinstance(content_str, str):
                    try:
                        content_data = json.loads(content_str)
                        tool_config_id = content_data.get("tool_config_id")
                    except Exception:
                        pass

        if not extracted_params and context.node_output:
            extracted_params = (
                context.node_output.get("extracted_params") or context.node_output
            )

        if config.get("output"):
            payload = config.get("output", {})
        elif tool_config_id and extracted_params:
            payload = {
                "tool_config_id": str(tool_config_id),
                "input": extracted_params,
                "execution_status": NodeExecutionStatus.SUCCESS,
                "expense_id": "exp_simulated_123456",
                "status": "created",
            }
        else:
            payload = {
                "execution_status": NodeExecutionStatus.SUCCESS,
                "expense_id": "exp_simulated_123456",
                "status": "created",
            }

        status = (
            NodeExecutionStatus.SUCCESS
            if payload.get("execution_status") == "SUCCESS"
            else NodeExecutionStatus.ERROR
        )

        return NodeResult(status=status, payload=payload)


class ClarificationNode(NodeExecutor):
    node_type = NodeType.ClarificationNode
    side_effect = False
    deterministic = True

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Request missing inputs."""
        payload = _payload_from_config(
            config, {"missing_fields": [], "user_message": ""}
        )
        return NodeResult(status=NodeExecutionStatus.NEEDS_INPUT, payload=payload)


class ResponseNode(NodeExecutor):
    node_type = NodeType.ResponseNode
    side_effect = False
    deterministic = True

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Return final response payload from previous node output."""

        config = config or {}

        if config.get("output"):
            payload = config.get("output", {})
        elif context.node_output:
            payload = {
                "system_output": context.node_output.get("system_output"),
                "payload": context.node_output,
            }
            if not payload.get("system_output"):
                payload["system_output"] = "Operação concluída com sucesso."
        else:
            payload = {"message": "ok", "payload": {}}

        return NodeResult(status=NodeExecutionStatus.SUCCESS, payload=payload)


class FallbackNode(NodeExecutor):
    node_type = NodeType.FallbackNode
    side_effect = False
    deterministic = True

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Return fallback payload."""
        payload = _payload_from_config(
            config, {"reason": "fallback", "message": "fallback"}
        )
        return NodeResult(status=NodeExecutionStatus.SUCCESS, payload=payload)
