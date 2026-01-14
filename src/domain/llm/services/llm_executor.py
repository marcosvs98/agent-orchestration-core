from __future__ import annotations

import time
import contextlib
from typing import Any, Dict, Callable
from uuid import UUID

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from domain.execution.repositories.execution_repository import ExecutionRepository
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.observability.event_payloads import (
    build_llm_call_completed_payload,
    build_llm_call_failed_payload,
    build_llm_call_started_payload,
    build_guardrail_blocked_payload,
    build_guardrail_checked_payload,
    build_guardrail_degraded_payload,
)
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.ports.llm_provider import LLMProviderPort
from domain.llm.schemas.llm import LLMRequest, LLMResult
from exceptions.service_exceptions import DomainValidationException
from domain.llm.services.circuit_breaker import CircuitBreaker
from domain.llm.services.cost_engine import CostEngine
from domain.llm.services.provider_selector import LLMProviderSelector, LLMProviderSelection
from domain.execution.services.guardrails.guardrail_engine import GuardrailEngine
from domain.execution.schemas.guardrails import GuardrailDecisionType
from adapters.observability.langfuse_runtime_tracer import LangfuseRuntimeTracer


class LLMExecutor(LLMExecutorPort):
    def __init__(
        self,
        provider: LLMProviderPort,
        repository: ExecutionRepository,
        *,
        circuit_breaker: CircuitBreaker | None = None,
        cost_engine: CostEngine | None = None,
        provider_selector: LLMProviderSelector | None = None,
        provider_factory: Callable[[LLMProviderSelection], LLMProviderPort] | None = None,
        guardrail_engine: GuardrailEngine | None = None,
        tracer: LangfuseRuntimeTracer | None = None,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.circuit_breaker = circuit_breaker
        self.cost_engine = cost_engine
        self.provider_selector = provider_selector
        self.provider_factory = provider_factory
        self.guardrail_engine = guardrail_engine
        self.tracer = tracer

    @staticmethod
    def _validate_schema(payload: Dict[str, Any], schema: Dict[str, Any], *, error_code: str) -> None:
        if not schema:
            return
        try:
            validate(instance=payload, schema=schema)
        except JsonSchemaValidationError as exc:
            raise DomainValidationException(message=error_code, detail=str(exc)) from exc

    @staticmethod
    def _enforce_policy(request: LLMRequest, result: LLMResult) -> None:
        if request.max_tokens is not None:
            used = sum(result.token_usage.values()) if result.token_usage else 0
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
    ) -> LLMResult:
        start_monotonic = time.monotonic()
        scope = f"{provider}:{tenant_id}"
        provider_model = request.model_alias
        provider_instance = self.provider
        if self.provider_selector and self.provider_factory:
            selection: LLMProviderSelection = await self.provider_selector.select(
                tenant_id=tenant_id, provider=provider, model_alias=request.model_alias
            )
            provider_model = selection.provider_model
            provider_instance = self.provider_factory(selection)
            request = request.model_copy(update={"model_alias": provider_model})
        if self.circuit_breaker:
            await self.circuit_breaker.ensure_closed(scope)

        guardrail_decision = None
        if self.guardrail_engine and policy_llm is not None:
            guardrail_decision = await self.guardrail_engine.check_and_reserve(
                tenant_id=tenant_id,
                flow_run_id=flow_run_id,
                request=request,
                policy_llm=policy_llm,
                provider=provider,
                provider_model=provider_model,
            )
            applied_limits = guardrail_decision.applied_limits or {}
            limit_label = ",".join(applied_limits.keys()) if applied_limits else "none"
            current_value = (
                applied_limits.get("projected_cost")
                or applied_limits.get("current_calls")
                or applied_limits.get("max_latency_ms_hard")
            )
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.GuardrailChecked,
                payload=build_guardrail_checked_payload(
                    guardrail_type="LLM",
                    decision=guardrail_decision.decision.value,
                    limit=limit_label,
                    current_value=current_value,
                    estimated_cost_usd=applied_limits.get("projected_cost"),
                    provider=provider,
                    model_alias=request.model_alias,
                    provider_model=provider_model,
                    trace_id=str(trace.trace_id),
                ),
                correlation_id=correlation_id,
                causation_id=None,
                schema_version=1,
                node_id=node_id,
                edge_id=None,
            )
            if guardrail_decision.decision is GuardrailDecisionType.BLOCK:
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.GuardrailBlocked,
                    payload=build_guardrail_blocked_payload(
                        guardrail_type="LLM",
                        limit=limit_label,
                        current_value=current_value,
                        reason_code=guardrail_decision.reason_code,
                        provider=provider,
                        model_alias=request.model_alias,
                        provider_model=provider_model,
                        trace_id=str(trace.trace_id),
                    ),
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
                if model_alias_override and self.provider_selector and self.provider_factory:
                    selection = await self.provider_selector.select(
                        tenant_id=tenant_id, provider=provider, model_alias=model_alias_override
                    )
                    provider_model = selection.provider_model
                    provider_instance = self.provider_factory(selection)
                    request = request.model_copy(update={"model_alias": provider_model})
                await self.repository.append_execution_event(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    event_type=ExecutionEventType.GuardrailDegraded,
                    payload=build_guardrail_degraded_payload(
                        guardrail_type="LLM",
                        limit=limit_label,
                        current_value=current_value,
                        reason_code=guardrail_decision.reason_code,
                        overrides=overrides,
                        provider=provider,
                        model_alias=request.model_alias,
                        provider_model=provider_model,
                        trace_id=str(trace.trace_id),
                    ),
                    correlation_id=correlation_id,
                    causation_id=None,
                    schema_version=1,
                    node_id=node_id,
                    edge_id=None,
                )
                max_latency_override = overrides.get("max_latency_ms")
                if max_latency_override:
                    request = request.model_copy(update={"max_latency_ms": max_latency_override})

        await self.repository.append_execution_event(
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            event_type=ExecutionEventType.LLMCallStarted,
            payload=build_llm_call_started_payload(
                task_type=request.task_type.value,
                model_alias=request.model_alias,
                provider_model=provider_model,
                provider=provider,
                trace_id=str(trace.trace_id),
            ),
            correlation_id=correlation_id,
            causation_id=None,
            schema_version=1,
            node_id=node_id,
            edge_id=None,
        )
        generation_cm = (
            self.tracer.start_llm_generation(
                model_id=provider_model,
                task_type=request.task_type.value,
                input={"input_keys": list(request.input_payload.keys())},
            )
            if self.tracer
            else contextlib.nullcontext()
        )
        try:
            self._validate_schema(request.input_payload, request.input_schema, error_code="llm_input_invalid")
            with generation_cm as generation_handle:
                provider_result = await provider_instance.infer(request)
                result = provider_result
                if result.latency_ms is None:
                    result = result.model_copy(
                        update={"latency_ms": int((time.monotonic() - start_monotonic) * 1000)}
                    )
                if self.cost_engine:
                    cost = await self.cost_engine.compute_cost(
                        provider=provider, provider_model=provider_model, token_usage=result.token_usage
                    )
                    result = result.model_copy(update={"cost_usd": cost})
                self._validate_schema(result.output, request.output_schema, error_code="llm_output_invalid")
                self._enforce_policy(request, result)
                if generation_handle:
                    generation_handle.update_success(
                        output=result.output,
                        token_usage=result.token_usage,
                        cost=result.cost_usd or 0.0,
                        latency_ms=result.latency_ms or 0,
                        model_version=provider_model,
                    )
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.LLMCallCompleted,
                payload=build_llm_call_completed_payload(
                    task_type=request.task_type.value,
                    model_alias=request.model_alias,
                    provider_model=provider_model,
                    provider=provider,
                    token_usage=result.token_usage,
                    cost_usd=result.cost_usd,
                    latency_ms=result.latency_ms,
                    trace_id=str(trace.trace_id),
                ),
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
            await self.repository.append_execution_event(
                tenant_id=tenant_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                event_type=ExecutionEventType.LLMCallFailed,
                payload=build_llm_call_failed_payload(
                    task_type=request.task_type.value,
                    model_alias=request.model_alias,
                    provider_model=provider_model,
                    provider=provider,
                    error_class=type(exc).__name__,
                    message=str(exc),
                    trace_id=str(trace.trace_id),
                ),
                correlation_id=correlation_id,
                causation_id=None,
                schema_version=1,
                node_id=node_id,
                edge_id=None,
            )
            raise exc from exc
