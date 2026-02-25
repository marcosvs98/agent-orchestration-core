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
    """Post-execution processor: extracts memory items from flow output via LLM and persists via MemoryWriteService."""

    def __init__(
        self,
        llm_executor: LLMExecutorPort | None,
        memory_write_service: Any,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.llm_executor = llm_executor
        self.memory_write_service = memory_write_service
        self.tracer = tracer

    def _resolve_task_type(
        self, task_type_value: str | LLMTaskType | None
    ) -> LLMTaskType:
        if isinstance(task_type_value, LLMTaskType):
            return task_type_value
        if not task_type_value or not isinstance(task_type_value, str):
            return _DEFAULT_LLM_TASK_TYPE
        key = task_type_value.strip()
        return _LLM_TASK_TYPE_BY_VALUE.get(key, _DEFAULT_LLM_TASK_TYPE)

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
        """Extract memory items from flow_output using config and write via memory_write_service."""
        try:
            config = MemoryExtractionConfig.model_validate(config_payload)
        except (ValidationError, TypeError):
            return
        if not config.enabled or not self.llm_executor or not self.memory_write_service:
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
            prompt = (
                config.llm.prompt
                or "Extract memory items from the provided flow output."
            )
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
            except Exception:
                if span_handle:
                    span_handle.failure()
                return
            raw_output = result.output if isinstance(result.output, dict) else {}
            try:
                parsed = MemoryExtractionLLMOutput.model_validate(raw_output)
            except (ValidationError, TypeError):
                if span_handle:
                    span_handle.failure(
                        output={"error": "llm_output_validation_failed"}
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
                if (
                    MemoryWriteTarget.USER_MEMORY_PROFILE
                    in write_result.targets_applied
                ):
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
