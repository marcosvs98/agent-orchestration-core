from __future__ import annotations

import json
from typing import Any, Dict
from uuid import UUID

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
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

            with self.tracer.observe(
                as_type="chain",
                name="domain.execution.nodes.intent_tool_selection.resolve_prompt",
                input={"node_id": str(node_uuid) if node_uuid else None},
            ):
                resolved_prompt = await self.prompt_resolver.resolve(
                    intent=PromptIntent.INTENT_TOOL_SELECTION,
                    context=context,
                    node_id=node_uuid,
                )

            task_type = LLMTaskType.INTENT_SELECTION

            request = LLMRequest(
                prompt=resolved_prompt.prompt_text,
                system_prompt=context.system_prompt,
                input_schema=resolved_prompt.input_schema
                or llm_cfg.get("input_schema", {}),
                output_schema=resolved_prompt.output_schema
                or llm_cfg.get("output_schema", {}),
                model_alias=model_alias,
                max_tokens=llm_policy.get("max_tokens"),
                max_latency_ms=llm_policy.get("max_latency_ms"),
                max_cost_usd=llm_policy.get("max_cost_usd"),
                retry_limit=llm_policy.get("retry_limit"),
                fallback_model_alias=llm_policy.get("fallback_model_alias"),
                available_tools=context.available_tools,
                prompt_id=str(resolved_prompt.prompt_id)
                if resolved_prompt.prompt_id
                else None,
                prompt_version=resolved_prompt.prompt_version,
                prompt_frozen_hash=resolved_prompt.prompt_frozen_hash,
                task_type=task_type,
            )
            with self.tracer.observe(
                as_type="generation",
                name="domain.execution.nodes.intent_tool_selection.execute_llm",
                input={"model_alias": model_alias, "provider": provider},
            ):
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

            task_type_raw = llm_cfg.get("task_type", LLMTaskType.SLOT_FILLING.value)
            try:
                task_type = LLMTaskType(task_type_raw)
            except ValueError:
                task_type = LLMTaskType.SLOT_FILLING

            intent = PromptIntent.SLOT_FILLING

            with self.tracer.observe(
                as_type="chain",
                name="domain.execution.nodes.param_extraction.resolve_prompt",
                input={"node_id": str(node_uuid) if node_uuid else None},
            ):
                resolved_prompt = await self.prompt_resolver.resolve(
                    intent=intent,
                    context=context,
                    node_id=node_uuid,
                )

            request = LLMRequest(
                prompt=resolved_prompt.prompt_text,
                system_prompt=context.system_prompt,
                input_schema=resolved_prompt.input_schema
                or llm_cfg.get("input_schema", {}),
                output_schema=resolved_prompt.output_schema
                or llm_cfg.get("output_schema", {}),
                model_alias=model_alias,
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
                task_type=task_type,
            )

            try:
                with self.tracer.observe(
                    as_type="generation",
                    name="domain.execution.nodes.param_extraction.execute_llm",
                    input={"model_alias": model_alias, "provider": provider},
                ):
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
            if isinstance(extracted_params, dict):
                payload = extracted_params.get("payload", extracted_params)
                missing_fields = extracted_params.get("missing_fields", [])
            else:
                payload = extracted_params
                missing_fields = []
            current_state = context.state or {}
            next_state = {
                **current_state,
                "extracted_params": payload,
                "missing_fields": missing_fields,
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
        missing_fields = payload.get("missing_fields", [])
        current_state = context.state or {}
        next_state = {
            **current_state,
            "extracted_params": payload.get("extracted_params", {}),
            "missing_fields": missing_fields,
            "intent_output": current_state.get("intent_output", {}),
        }

        return NodeResult(
            status=NodeExecutionStatus.SUCCESS, payload=payload, next_state=next_state
        )


class ToolExecutionNode(NodeExecutor):
    node_type = NodeType.ToolExecutionNode
    side_effect = True
    deterministic = False

    def __init__(
        self,
        tracer: RuntimeTracerPort,
        tool_orchestrator: Any | None = None,
        execution_repository: Any | None = None,
    ) -> None:
        self.tool_orchestrator = tool_orchestrator
        self.execution_repository = execution_repository
        self.tracer = tracer

    async def execute(
        self, context: ExecutionContext, config: Dict[str, Any] | None = None
    ) -> NodeResult:
        """Execute tool using ToolOrchestrator with tool_config_id and extracted parameters."""
        config = config or {}

        if config.get("output"):
            return NodeResult(
                status=NodeExecutionStatus.SUCCESS,
                payload=config.get("output", {}),
            )

        current_state = context.state or {}
        intent_output = current_state.get("intent_output") or {}
        extracted_params = current_state.get("extracted_params") or {}
        tool_config_id = intent_output.get("tool_config_id")

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

        if not tool_config_id:
            return NodeResult(
                status=NodeExecutionStatus.ERROR,
                payload={},
                error={"message": "tool_config_id_not_found"},
            )

        if not self.tool_orchestrator or not self.execution_repository:
            return NodeResult(
                status=NodeExecutionStatus.ERROR,
                payload={},
                error={"message": "tool_orchestrator_not_configured"},
            )

        if not context.current_node_run_id:
            return NodeResult(
                status=NodeExecutionStatus.ERROR,
                payload={},
                error={"message": "node_run_id_not_available"},
            )

        try:
            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.nodes.tool_execution.create_tool_run",
                input={"tool_config_id": str(tool_config_id)},
            ):
                tool_run_id = await self.execution_repository.create_tool_run(
                    tool_config_id=UUID(str(tool_config_id)),
                    correlation_id=context.correlation_id,
                    agent_run_id=None,
                    node_run_id=context.current_node_run_id,
                    idempotency_key=None,
                    has_side_effect=True,
                    input_payload=extracted_params,
                )

            with self.tracer.observe(
                as_type="tool",
                name="domain.execution.nodes.tool_execution.execute_tool_run",
                input={"tool_run_id": str(tool_run_id)},
            ):
                result = await self.tool_orchestrator.execute_tool_run(
                    tool_run_id=tool_run_id
                )

            payload = {
                "tool_run_id": str(tool_run_id),
                "tool_config_id": str(tool_config_id),
                "input": extracted_params,
                "output": result,
                "execution_status": NodeExecutionStatus.SUCCESS,
            }

            return NodeResult(status=NodeExecutionStatus.SUCCESS, payload=payload)

        except Exception as exc:
            return NodeResult(
                status=NodeExecutionStatus.ERROR,
                payload={
                    "tool_config_id": str(tool_config_id),
                    "input": extracted_params,
                    "execution_status": NodeExecutionStatus.ERROR,
                },
                error={"message": str(exc), "error_type": type(exc).__name__},
            )


class ClarificationNode(NodeExecutor):
    node_type = NodeType.ClarificationNode
    side_effect = False
    deterministic = True

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
        """Request missing inputs."""
        config = config or {}
        llm_cfg = config.get("llm")

        if llm_cfg and context:
            if not self.prompt_resolver or not self.llm_executor:
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

            with self.tracer.observe(
                as_type="chain",
                name="domain.execution.nodes.clarification.resolve_prompt",
                input={"node_id": str(node_uuid) if node_uuid else None},
            ):
                resolved_prompt = await self.prompt_resolver.resolve(
                    intent=PromptIntent.CLARIFICATION,
                    context=context,
                    node_id=node_uuid,
                )

            request = LLMRequest(
                prompt=resolved_prompt.prompt_text,
                system_prompt=context.system_prompt,
                input_schema=resolved_prompt.input_schema
                or llm_cfg.get("input_schema", {}),
                output_schema=resolved_prompt.output_schema
                or llm_cfg.get("output_schema", {}),
                model_alias=model_alias,
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
                task_type=LLMTaskType.CLARIFICATION,
            )

            with self.tracer.observe(
                as_type="generation",
                name="domain.execution.nodes.clarification.execute_llm",
                input={"model_alias": model_alias, "provider": provider},
            ):
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
            payload = result.output or {}
            return NodeResult(
                status=NodeExecutionStatus.NEEDS_INPUT,
                payload=payload,
                metrics=result.token_usage,
            )

        payload = _payload_from_config(
            config, {"missing_fields": [], "user_message": ""}
        )
        return NodeResult(status=NodeExecutionStatus.NEEDS_INPUT, payload=payload)


class ResponseNode(NodeExecutor):
    node_type = NodeType.ResponseNode
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

        if config.get("output"):
            return NodeResult(
                status=NodeExecutionStatus.SUCCESS,
                payload=config.get("output", {}),
            )

        llm_cfg = config.get("llm")

        if not llm_cfg or not self.llm_executor or not self.prompt_resolver:
            return NodeResult(
                status=NodeExecutionStatus.ERROR,
                payload={},
                error={"message": "llm_config_required"},
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
            return NodeResult(
                status=NodeExecutionStatus.ERROR,
                payload={},
                error={"message": "llm_model_alias_required"},
            )

        try:
            node_uuid: UUID | None = UUID(context.current_node_id)
        except Exception:
            node_uuid = None

        task_type_raw = llm_cfg.get("task_type", LLMTaskType.RESPONSE_RENDER.value)
        try:
            task_type = LLMTaskType(task_type_raw)
        except ValueError:
            task_type = LLMTaskType.RESPONSE_RENDER

        with self.tracer.observe(
            as_type="chain",
            name="domain.execution.nodes.response.resolve_prompt",
            input={"node_id": str(node_uuid) if node_uuid else None},
        ):
            resolved_prompt = await self.prompt_resolver.resolve(
                intent=PromptIntent.RESPONSE_RENDER,
                context=context,
                node_id=node_uuid,
            )

        request = LLMRequest(
            prompt=resolved_prompt.prompt_text,
            system_prompt=context.system_prompt,
            input_schema=resolved_prompt.input_schema
            or llm_cfg.get("input_schema", {}),
            output_schema=resolved_prompt.output_schema
            or llm_cfg.get("output_schema", {}),
            model_alias=model_alias,
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
            task_type=task_type,
        )

        with self.tracer.observe(
            as_type="generation",
            name="domain.execution.nodes.response.execute_llm",
            input={"model_alias": model_alias, "provider": provider},
        ):
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

        llm_output = result.output or {}
        system_output = (
            llm_output.get("system_output")
            if isinstance(llm_output, dict)
            else str(llm_output)
        )

        return NodeResult(
            status=NodeExecutionStatus.SUCCESS,
            payload={
                "system_output": system_output,
                "payload": context.node_output,
            },
        )


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
