from __future__ import annotations

import time
from datetime import UTC, datetime

from collections.abc import Awaitable
from typing import Any, Dict, Callable
from uuid import UUID
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.observability.event_payloads import (
    GuardrailBlockedPayload,
    GuardrailCheckedPayload,
    GuardrailDegradedPayload,
    LLMCallCompletedPayload,
    LLMCallFailedPayload,
    LLMCallStartedPayload,
)
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMRequest, LLMResult
from exceptions.service_exceptions import DomainValidationException
from domain.llm.services.circuit_breaker import CircuitBreaker
from domain.llm.services.cost_engine import CostEngine
from domain.llm.services.provider_selector import (
    LLMProviderSelector,
    LLMProviderSelection,
)
from domain.execution.services.guardrails.guardrail_engine import GuardrailEngine
from domain.execution.schemas.guardrails import GuardrailDecisionType
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
import orjson
from domain.execution.services.observability.event_payloads import (
    NodePromptExecutedPayload,
)


class LLMExecutor(LLMExecutorPort):
    def __init__(
        self,
        repository: ExecutionRepository,
        provider: LLMProviderPort | None = None,
        *,
        circuit_breaker: CircuitBreaker | None = None,
        cost_engine: CostEngine | None = None,
        provider_selector: LLMProviderSelector | None = None,
        provider_factory: Callable[[LLMProviderSelection], LLMProviderPort] | None = None,
        guardrail_engine: GuardrailEngine | None = None,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.circuit_breaker = circuit_breaker
        self.cost_engine = cost_engine
        self.provider_selector = provider_selector
        self.provider_factory = provider_factory
        self.guardrail_engine = guardrail_engine
        self.tracer = tracer

    def _validate_schema(
        self, payload: Dict[str, Any], schema: Dict[str, Any], *, error_code: str
    ) -> None:
        if not schema:
            return

        evaluator_handle = None
        validation_exc = None
        try:
            with self.tracer.observe(
                as_type="evaluator",
                name="evaluator.schema_validation",
                input={
                    "payload": payload,
                    "schema": schema,
                },
                metadata={"evaluator_name": "schema_validation"},
            ) as evaluator_handle:
                try:
                    validate(instance=payload, schema=schema)
                    if evaluator_handle:
                        evaluator_handle.success(output={"passed": True, "errors": []})
                except JsonSchemaValidationError as exc:
                    validation_exc = exc
                    error_message = str(exc)
                    if evaluator_handle:
                        evaluator_handle.error(
                            error_type=type(exc).__name__,
                            error_message=error_message,
                            output={"passed": False, "errors": [error_message]},
                        )
                except Exception as exc:
                    validation_exc = exc
                    if evaluator_handle:
                        evaluator_handle.error(
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            output={"passed": False, "errors": [str(exc)]},
                        )
        except Exception as cm_exc:
            if validation_exc:
                if isinstance(validation_exc, JsonSchemaValidationError):
                    raise DomainValidationException(
                        message=error_code, detail=str(validation_exc)
                    ) from validation_exc
                raise DomainValidationException(
                    message="internal_schema_validation_error",
                    detail=str(validation_exc),
                ) from validation_exc
            raise DomainValidationException(
                message="internal_schema_validation_error", detail=str(cm_exc)
            ) from cm_exc

        if validation_exc:
            if isinstance(validation_exc, JsonSchemaValidationError):
                raise DomainValidationException(
                    message=error_code, detail=str(validation_exc)
                ) from validation_exc
            raise DomainValidationException(
                message="internal_schema_validation_error", detail=str(validation_exc)
            ) from validation_exc

    @staticmethod
    def _enforce_policy(request: LLMRequest, result: LLMResult) -> None:
        if request.max_tokens is not None:
            token_usage = result.token_usage or {}
            completion_tokens = token_usage.get("completion_tokens")
            if completion_tokens is None:
                completion_tokens = token_usage.get("output_tokens")
            if completion_tokens is None:
                completion_tokens = token_usage.get("total_tokens")
            used = completion_tokens if isinstance(completion_tokens, (int, float)) else 0
            if used > request.max_tokens:
                raise DomainValidationException(message="llm_policy_max_tokens_exceeded")
        if request.max_cost_usd is not None and result.cost_usd is not None:
            if result.cost_usd > request.max_cost_usd:
                raise DomainValidationException(message="llm_policy_cost_exceeded")
        if request.max_latency_ms is not None and result.latency_ms is not None:
            if result.latency_ms > request.max_latency_ms:
                raise DomainValidationException(message="llm_policy_latency_exceeded")

    async def execute_llm(
        self,
        *,
        request: LLMRequest,
        trace: TraceContext,
        tenant_id: UUID,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        node_id: UUID | None = None,
        provider: str = "OPENAI",
        policy_llm: Dict[str, Any] | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResult:
        start_monotonic = time.monotonic()
        scope = f"{provider}:{tenant_id}"
        provider_model = request.model_alias
        provider_instance = self.provider
        if self.provider_selector and self.provider_factory:
            with self.tracer.observe(
                as_type="agent",
                name="domain.llm.llm_executor.select_provider",
                input={
                    "tenant_id": str(tenant_id),
                    "provider": provider,
                    "model_alias": request.model_alias,
                },
            ) as selection_handle:
                selection: LLMProviderSelection = await self.provider_selector.select(
                    tenant_id=tenant_id,
                    provider=provider,
                    model_alias=request.model_alias,
                )
                provider_model = selection.provider_model
                provider_instance = self.provider_factory(selection)
                request = request.model_copy(update={"model_alias": provider_model})
                if selection_handle:
                    selection_handle.success(
                        output={
                            "provider_model": provider_model,
                            "provider": provider,
                        }
                    )

        if provider_instance is None:
            raise DomainValidationException(
                message="llm_provider_not_configured",
                detail="No LLM provider available. Either provide a default provider or configure provider_selector and provider_factory.",
            )
        if self.circuit_breaker:
            with self.tracer.observe(
                as_type="guardrail",
                name="domain.llm.llm_executor.circuit_breaker_check",
                input={"scope": scope},
            ) as circuit_handle:
                await self.circuit_breaker.ensure_closed(scope)
                if circuit_handle:
                    circuit_handle.success(output={"status": "closed"})

        guardrail_decision = None

        prompt_version = request.prompt_version
        prompt_frozen_hash = request.prompt_frozen_hash
        prompt_id = request.prompt_id
        task_type_value = request.task_type.value if request.task_type else None

        payload: LLMCallStartedPayload = LLMCallStartedPayload(
            task_type=task_type_value,
            model_alias=request.model_alias,
            provider_model=provider_model,
            provider=provider,
            trace_id=str(trace.trace_id),
        )
        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.LLMCallStarted,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
            node_id=node_id,
            edge_id=None,
        )

        model_parameters = {}
        if request.max_tokens:
            model_parameters["max_tokens"] = request.max_tokens
        if policy_llm:
            if policy_llm.get("temperature") is not None:
                model_parameters["temperature"] = policy_llm.get("temperature")
            if policy_llm.get("top_p") is not None:
                model_parameters["top_p"] = policy_llm.get("top_p")

        execution_metadata = {}
        if prompt_id:
            execution_metadata["prompt_id"] = prompt_id
        if prompt_version is not None:
            execution_metadata["prompt_version"] = prompt_version
        if prompt_frozen_hash:
            execution_metadata["prompt_frozen_hash"] = prompt_frozen_hash
            execution_metadata["prompt_hash"] = prompt_frozen_hash
        if task_type_value:
            execution_metadata["llm_task"] = task_type_value
        if request.user_id:
            execution_metadata["user_id"] = request.user_id

        llm_input: Dict[str, Any] = {
            "prompt": request.prompt,
            "system_prompt": request.system_prompt,
            "provider_model": provider_model,
            "provider": provider,
        }
        if request.system_context:
            llm_input["system_context"] = request.system_context
        if request.user_payload:
            llm_input["user_payload"] = request.user_payload
        if request.input_payload:
            llm_input["input_payload"] = request.input_payload
        if request.user_message:
            llm_input["user_message"] = request.user_message
        if request.messages:
            llm_input["messages"] = [m.model_dump(mode="json") for m in request.messages]
        if task_type_value:
            llm_input["task_type"] = task_type_value
        if request.user_id:
            llm_input["user_id"] = request.user_id
        if request.max_tokens is not None:
            llm_input["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            llm_input["temperature"] = request.temperature
        if request.available_tools:
            llm_input["tools_count"] = len(request.available_tools)
        if prompt_id:
            llm_input["prompt_id"] = prompt_id
        if prompt_version is not None:
            llm_input["prompt_version"] = prompt_version
        if request.conversation_key:
            llm_input["conversation_key"] = request.conversation_key

        chain_handler = None
        try:
            with self.tracer.observe(
                as_type="chain",
                name=f"domain.llm.llm_executor.{task_type_value.lower()}",
                input=llm_input,
                metadata=execution_metadata,
                model=provider_model,
                model_parameters=model_parameters or None,
                completion_start_time=datetime.now(UTC),
            ) as chain_handler:
                try:
                    self._validate_schema(
                        request.user_payload
                        or request.input_payload
                        or (
                            {"user_message": request.user_message}
                            if request.user_message
                            else {"prompt": request.prompt}
                        ),
                        request.input_schema,
                        error_code="llm_input_invalid",
                    )
                    guardrail_decision = None
                    if self.guardrail_engine and policy_llm is not None:
                        with self.tracer.observe(
                            as_type="guardrail",
                            name="guardrail.llm",
                            input={
                                "provider": provider,
                                "provider_model": provider_model,
                            },
                            metadata={"guardrail_type": "LLM"},
                        ) as guardrail_handle:
                            guardrail_decision = await self.guardrail_engine.check_and_reserve(
                                tenant_id=tenant_id,
                                flow_run_id=flow_run_id,
                                request=request,
                                policy_llm=policy_llm,
                                provider=provider,
                                provider_model=provider_model,
                            )
                            guardrail_output = {
                                "decision": guardrail_decision.decision.value,
                                "reason_code": guardrail_decision.reason_code,
                                "applied_limits": guardrail_decision.applied_limits or {},
                                "overrides": guardrail_decision.overrides,
                            }
                            if guardrail_handle:
                                if guardrail_decision.decision is GuardrailDecisionType.BLOCK:
                                    guardrail_handle.update(
                                        level="ERROR",
                                        status_message=f"Guardrail blocked: {guardrail_decision.reason_code}",
                                        output=guardrail_output,
                                    )
                                else:
                                    guardrail_handle.success(output=guardrail_output)

                        applied_limits = guardrail_decision.applied_limits or {}
                        limit_label = ",".join(applied_limits.keys()) if applied_limits else "none"
                        current_value = (
                            applied_limits.get("projected_cost")
                            or applied_limits.get("current_calls")
                            or applied_limits.get("max_latency_ms_hard")
                        )
                        payload: GuardrailCheckedPayload = GuardrailCheckedPayload(
                            guardrail_type="LLM",
                            decision=guardrail_decision.decision.value,
                            limit=limit_label,
                            current_value=current_value,
                            estimated_cost_usd=applied_limits.get("projected_cost"),
                            provider=provider,
                            model_alias=request.model_alias,
                            provider_model=provider_model,
                            trace_id=str(trace.trace_id),
                        )
                        await self.repository.append_execution_event(
                            tenant_id=tenant_id,
                            session_id=session_id,
                            flow_run_id=flow_run_id,
                            event_type=ExecutionEventType.GuardrailChecked,
                            payload=payload,
                            correlation_id=correlation_id,
                            causation_id=None,
                            schema_version=1,
                            node_id=node_id,
                            edge_id=None,
                        )
                        if guardrail_decision.decision is GuardrailDecisionType.BLOCK:
                            payload = GuardrailBlockedPayload(
                                guardrail_type="LLM",
                                limit=limit_label,
                                current_value=current_value,
                                reason_code=guardrail_decision.reason_code,
                                provider=provider,
                                model_alias=request.model_alias,
                                provider_model=provider_model,
                                trace_id=str(trace.trace_id),
                            )
                            await self.repository.append_execution_event(
                                tenant_id=tenant_id,
                                session_id=session_id,
                                flow_run_id=flow_run_id,
                                event_type=ExecutionEventType.GuardrailBlocked,
                                payload=payload,
                                correlation_id=correlation_id,
                                causation_id=None,
                                schema_version=1,
                                node_id=node_id,
                                edge_id=None,
                            )
                            raise DomainValidationException(message="guardrail_blocked")
                        if guardrail_decision.decision is GuardrailDecisionType.DEGRADE:
                            overrides = guardrail_decision.overrides or {}
                            model_alias_override = overrides.get("model_alias")
                            if (
                                model_alias_override
                                and self.provider_selector
                                and self.provider_factory
                            ):
                                selection = await self.provider_selector.select(
                                    tenant_id=tenant_id,
                                    provider=provider,
                                    model_alias=model_alias_override,
                                )
                                provider_model = selection.provider_model
                                provider_instance = self.provider_factory(selection)
                                request = request.model_copy(update={"model_alias": provider_model})
                            sanitized_overrides: Dict[str, Any] = {}
                            for key, value in overrides.items():
                                if isinstance(value, (str, int, float, bool)) or value is None:
                                    sanitized_overrides[key] = value
                                else:
                                    sanitized_overrides[key] = str(value)
                            payload = GuardrailDegradedPayload(
                                guardrail_type="LLM",
                                limit=limit_label,
                                current_value=current_value,
                                reason_code=guardrail_decision.reason_code,
                                overrides=sanitized_overrides,
                                provider=provider,
                                model_alias=request.model_alias,
                                provider_model=provider_model,
                                trace_id=str(trace.trace_id),
                            )
                            await self.repository.append_execution_event(
                                tenant_id=tenant_id,
                                session_id=session_id,
                                flow_run_id=flow_run_id,
                                event_type=ExecutionEventType.GuardrailDegraded,
                                payload=payload,
                                correlation_id=correlation_id,
                                causation_id=None,
                                schema_version=1,
                                node_id=node_id,
                                edge_id=None,
                            )
                            max_latency_override = overrides.get("max_latency_ms")
                            if max_latency_override:
                                request = request.model_copy(
                                    update={"max_latency_ms": max_latency_override}
                                )

                    completion_start = datetime.now(UTC)
                    with self.tracer.observe(
                        as_type="generation",
                        name=f"domain.llm.llm_executor.infer.{task_type_value.lower() or 'infer'}".lower(),
                        input=llm_input,
                        metadata=execution_metadata,
                        model=provider_model,
                        model_parameters=model_parameters or None,
                        completion_start_time=completion_start,
                    ) as generation_handle:
                        try:
                            provider_result = await provider_instance.infer(
                                request, on_delta=on_delta
                            )
                            result = provider_result
                            if result.pipeline_latency_ms is None:
                                result = result.model_copy(
                                    update={
                                        "pipeline_latency_ms": int(
                                            (time.monotonic() - start_monotonic) * 1000
                                        )
                                    }
                                )
                            if self.cost_engine:
                                cost = await self.cost_engine.compute_cost(
                                    provider=provider,
                                    provider_model=provider_model,
                                    token_usage=result.token_usage,
                                )
                                result = result.model_copy(update={"cost_usd": cost})
                            if generation_handle:
                                usage_details = {
                                    "prompt_tokens": result.token_usage.get("prompt_tokens")
                                    or result.token_usage.get("input_tokens")
                                    or 0,
                                    "completion_tokens": result.token_usage.get("completion_tokens")
                                    or result.token_usage.get("output_tokens")
                                    or 0,
                                    "total_tokens": result.token_usage.get("total_tokens") or 0,
                                }
                                cost_details = (
                                    {"total_cost": result.cost_usd}
                                    if result.cost_usd is not None
                                    else None
                                )
                                generation_handle.success(
                                    output=result.output,
                                    usage_details=usage_details,
                                    cost_details=cost_details,
                                    metadata={
                                        "latency_ms": result.latency_ms,
                                        "pipeline_latency_ms": result.pipeline_latency_ms,
                                        "model_used": result.model_alias or provider_model,
                                        "provider": provider,
                                        "cost_usd": result.cost_usd,
                                    },
                                )

                        except Exception as infer_exc:
                            if generation_handle:
                                if isinstance(infer_exc, DomainValidationException):
                                    generation_handle.error(
                                        error_type=type(infer_exc).__name__,
                                        error_message=str(infer_exc),
                                        output={
                                            "status": "error",
                                            "errors": infer_exc.errors,
                                            "input_data": infer_exc.input_data,
                                        },
                                    )
                                    raise infer_exc from infer_exc

                                generation_handle.error(
                                    error_type=type(infer_exc).__name__,
                                    error_message=str(infer_exc),
                                    output={
                                        "status": "error",
                                    },
                                )
                            raise infer_exc from infer_exc

                    output_to_validate = result.output
                    if isinstance(result.output, str):
                        try:
                            output_to_validate = orjson.loads(result.output)
                            result = result.model_copy(update={"output": output_to_validate})
                        except orjson.JSONDecodeError as json_exc:
                            raise DomainValidationException(
                                message="llm_output_json_parse_error",
                                detail=f"Failed to parse JSON output: {str(json_exc)}",
                            ) from json_exc
                    elif (
                        isinstance(result.output, dict)
                        and "content" in result.output
                        and len(result.output.keys()) == 1
                    ):
                        content_str = result.output.get("content")
                        if isinstance(content_str, str):
                            try:
                                parsed_content = orjson.loads(content_str)
                                output_to_validate = parsed_content
                                result = result.model_copy(update={"output": parsed_content})
                            except orjson.JSONDecodeError as json_exc:
                                raise DomainValidationException(
                                    message="llm_output_json_parse_error",
                                    detail=f"Failed to parse JSON content: {str(json_exc)}",
                                ) from json_exc

                    try:
                        self._validate_schema(
                            output_to_validate,
                            request.output_schema,
                            error_code="llm_output_invalid",
                        )
                    except Exception as schema_exc:
                        raise schema_exc from schema_exc
                    self._enforce_policy(request, result)

                    if chain_handler:
                        usage_details = {
                            "prompt_tokens": result.token_usage.get("prompt_tokens")
                            or result.token_usage.get("input_tokens")
                            or 0,
                            "completion_tokens": result.token_usage.get("completion_tokens")
                            or result.token_usage.get("output_tokens")
                            or 0,
                            "total_tokens": result.token_usage.get("total_tokens") or 0,
                        }
                        cost_details = (
                            {"total_cost": result.cost_usd} if result.cost_usd is not None else None
                        )
                        chain_handler.success(
                            output=result.output,
                            usage_details=usage_details,
                            cost_details=cost_details,
                            metadata={
                                "latency_ms": result.latency_ms,
                                "pipeline_latency_ms": result.pipeline_latency_ms,
                                "model_used": result.model_alias or provider_model,
                                "provider": provider,
                                "cost_usd": result.cost_usd,
                            },
                        )
                except Exception as exc:
                    if chain_handler:
                        chain_handler.error(
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                            output={"status": "error"},
                        )
                    raise

            sanitized_usage: Dict[str, int | float | None] = {}
            for key, value in (result.token_usage or {}).items():
                if isinstance(value, (int, float)) or value is None:
                    sanitized_usage[key] = value
                else:
                    sanitized_usage[key] = None
            payload: LLMCallCompletedPayload = LLMCallCompletedPayload(
                task_type=request.task_type.value,
                model_alias=request.model_alias,
                provider_model=provider_model,
                provider=provider,
                token_usage=sanitized_usage,
                cost_usd=result.cost_usd,
                latency_ms=result.latency_ms,
                trace_id=str(trace.trace_id),
            )
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.LLMCallCompleted,
                payload=payload,
                correlation_id=correlation_id,
                causation_id=None,
                schema_version=1,
                node_id=node_id,
                edge_id=None,
            )
            if prompt_version and prompt_frozen_hash:
                payload: NodePromptExecutedPayload = NodePromptExecutedPayload(
                    node_type=None,
                    prompt_version=prompt_version,
                    frozen_hash=prompt_frozen_hash,
                    token_usage=sanitized_usage,
                    latency_ms=result.latency_ms,
                    cost_usd=result.cost_usd,
                )
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.NodePromptExecuted,
                    payload=payload,
                    correlation_id=correlation_id,
                    causation_id=None,
                    schema_version=1,
                    node_id=node_id,
                    edge_id=None,
                )
            if self.guardrail_engine and policy_llm is not None:
                await self.guardrail_engine.record_post_call_cost(
                    tenant_id=tenant_id,
                    flow_run_id=flow_run_id,
                    cost_usd=result.cost_usd,
                    policy_llm=policy_llm,
                )
            if self.circuit_breaker:
                await self.circuit_breaker.record_success(scope)
            return result
        except Exception as exc:  # noqa: BLE001
            if self.circuit_breaker:
                await self.circuit_breaker.record_failure(scope)
            payload: LLMCallFailedPayload = LLMCallFailedPayload(
                task_type=task_type_value,
                model_alias=request.model_alias,
                provider_model=provider_model,
                provider=provider,
                error_class=type(exc).__name__,
                message=str(exc),
                trace_id=str(trace.trace_id),
            )
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.LLMCallFailed,
                payload=payload,
                correlation_id=correlation_id,
                causation_id=None,
                schema_version=1,
                node_id=node_id,
                edge_id=None,
            )
            raise exc from exc
