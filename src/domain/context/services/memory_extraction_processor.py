from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from domain.context.schemas.memory_extraction import (
    MemoryExtractionConfig,
    MemoryExtractionLLMOutput,
    MemoryExtractionSummary,
)
from domain.context.schemas.memory_write import MemoryWriteEventContext
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.trace import TraceContext
from domain.governance.schemas.memory_policy import (
    MemoryPolicySource,
    MemoryWriteTarget,
)
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import LLMRequest, LLMResult, LLMTaskType
from pydantic import ValidationError

_LLM_TASK_TYPE_BY_VALUE: dict[str, LLMTaskType] = {t.value: t for t in LLMTaskType}
_DEFAULT_LLM_TASK_TYPE = LLMTaskType.MEMORY_EXTRACTION


class MemoryExtractionProcessor:
    def __init__(
        self,
        llm_executor: LLMExecutorPort | None,
        memory_write_service: Any,
        tracer: RuntimeTracerPort,
        memory_policy_service: Any,
    ) -> None:
        self.llm_executor = llm_executor
        self.memory_write_service = memory_write_service
        self.tracer = tracer
        self.memory_policy_service = memory_policy_service

    @staticmethod
    def _resolve_task_type(task_type_value: str | LLMTaskType | None) -> LLMTaskType:
        if task_type_value is None:
            return _DEFAULT_LLM_TASK_TYPE
        if task_type_value in LLMTaskType:
            return LLMTaskType(str(task_type_value))
        key = str(task_type_value).strip()
        if not key:
            return _DEFAULT_LLM_TASK_TYPE
        return _LLM_TASK_TYPE_BY_VALUE.get(key, _DEFAULT_LLM_TASK_TYPE)

    def _emit_skipped(self, tenant_id: UUID, flow_run_id: UUID, reason_code: str) -> None:
        with self.tracer.observe(
            as_type="span",
            name="domain.context.memory_extraction.skipped",
            input={
                "tenant_id": str(tenant_id),
                "flow_run_id": str(flow_run_id),
                "reason_code": reason_code,
            },
        ) as handle:
            if handle:
                handle.success(output={"reason_code": reason_code})

    async def execute(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        flow_output: dict[str, Any],
        config_payload: dict[str, Any],
        event_context: MemoryWriteEventContext,
        trace_id: UUID,
    ) -> None:
        try:
            config = MemoryExtractionConfig.model_validate(config_payload)
        except (ValidationError, TypeError):
            self._emit_skipped(tenant_id, flow_run_id, "invalid_config")
            return
        if not config.enabled:
            self._emit_skipped(tenant_id, flow_run_id, "disabled")
            return
        if not self.llm_executor:
            self._emit_skipped(tenant_id, flow_run_id, "missing_llm_executor")
            return
        if not self.memory_write_service:
            self._emit_skipped(tenant_id, flow_run_id, "missing_memory_write_service")
            return
        resolved_memory = await self.memory_policy_service.resolve(
            tenant_id=tenant_id,
        )
        definition = resolved_memory.definition
        allowed_sources = definition.allowed_sources if definition is not None else []
        if MemoryPolicySource.INFERRED_LLM not in allowed_sources:
            self._emit_skipped(tenant_id, flow_run_id, "inferred_llm_not_allowed")
            return

        with self.tracer.observe(
            as_type="span",
            name="domain.context.memory_extraction_processor.execute",
            input={
                "tenant_id": str(tenant_id),
                "flow_run_id": str(flow_run_id),
                "config_enabled": config.enabled,
            },
        ) as span_handle:
            trace = TraceContext(
                trace_id=trace_id,
                flow_run_id=flow_run_id,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                correlation_id=correlation_id,
            )
            llm_input = json.dumps(flow_output, ensure_ascii=True)
            prompt = config.llm.prompt or "Extract memory items from the provided flow output."
            request = LLMRequest(
                prompt=prompt,
                user_message=llm_input,
                user_payload={"flow_output": llm_input},
                output_schema=MemoryExtractionLLMOutput.model_json_schema(),
                json_schema=MemoryExtractionLLMOutput.model_json_schema(),
                json_schema_name="memory_extraction_output",
                input_schema=config.llm.input_schema or {},
                model_alias=config.llm.model_alias,
                max_tokens=config.llm.max_tokens,
                max_latency_ms=config.llm.max_latency_ms,
                max_cost_usd=config.llm.max_cost_usd,
                retry_limit=config.llm.retry_limit,
                task_type=self._resolve_task_type(config.llm.task_type),
                user_id=user_id,
            )
            try:
                result: LLMResult = await self.llm_executor.execute_llm(
                    request=request,
                    trace=trace,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    flow_run_id=flow_run_id,
                    correlation_id=correlation_id,
                    node_id=None,
                    provider=config.llm.provider.value,
                    policy_llm=None,
                )
            except Exception as exc:
                if span_handle:
                    span_handle.error(
                        error_type=exc.__class__.__name__,
                        error_message="llm_generation_failed",
                    )
                return
            raw_out = result.output
            if raw_out is None:
                raw_output: dict[str, Any] = {}
            elif type(raw_out) is dict:
                raw_output = raw_out
            else:
                raw_output = {}
            try:
                parsed = MemoryExtractionLLMOutput.model_validate(raw_output)
            except (ValidationError, TypeError) as exc:
                if span_handle:
                    span_handle.error(
                        error_type=exc.__class__.__name__,
                        error_message="llm_output_validation_failed",
                    )
                return
            summary = MemoryExtractionSummary()
            for pref in parsed.preferences:
                summary.attempted_preferences += 1
                item = {
                    "schema_id": config.preference_schema_id,
                    "schema_version": 1,
                    "data": {
                        "preference_key": pref.preference_key or "",
                        "preference_value": pref.preference_value,
                    },
                    "source": MemoryPolicySource.INFERRED_LLM,
                    "observed_at": None,
                    "rag_config_id": config.rag_config_id,
                }
                write_result = await self.memory_write_service.write_memory_item(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    item=item,
                    event_context=event_context,
                )
                if MemoryWriteTarget.USER_PREFERENCE in write_result.targets_applied:
                    summary.applied_preferences += 1
                else:
                    summary.ignored_preferences += 1
            if parsed.profile_patch:
                summary.attempted_profile += 1
                item = {
                    "schema_id": config.profile_schema_id,
                    "schema_version": 1,
                    "data": {"profile_patch": parsed.profile_patch},
                    "source": MemoryPolicySource.INFERRED_LLM,
                    "observed_at": None,
                    "rag_config_id": config.rag_config_id,
                }
                write_result = await self.memory_write_service.write_memory_item(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    item=item,
                    event_context=event_context,
                )
                if MemoryWriteTarget.USER_MEMORY_PROFILE in write_result.targets_applied:
                    summary.applied_profile += 1
                else:
                    summary.ignored_profile += 1
            for vec in parsed.vector_memory:
                summary.attempted_vector += 1
                item = {
                    "schema_id": vec.schema_id,
                    "schema_version": vec.schema_version,
                    "data": vec.data,
                    "source": MemoryPolicySource.INFERRED_LLM,
                    "observed_at": None,
                    "rag_config_id": config.rag_config_id,
                }
                write_result = await self.memory_write_service.write_memory_item(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    item=item,
                    event_context=event_context,
                )
                if MemoryWriteTarget.USER_MEMORY_VECTOR in write_result.targets_applied:
                    summary.applied_vector += 1
                else:
                    summary.ignored_vector += 1
            if span_handle:
                span_handle.success(
                    output={
                        "summary": summary.model_dump(mode="json"),
                    },
                )
