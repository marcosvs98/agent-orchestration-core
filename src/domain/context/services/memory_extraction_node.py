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
from domain.context.services.memory_writer import MemoryWriteService
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.trace import TraceContext
from domain.execution.services.graph_runtime.types import NodeExecutionStatus, NodeResult
from domain.llm.ports.llm_executor import LLMExecutorPort
from domain.llm.schemas.llm import LLMRequest, LLMTaskType
from exceptions.service_exceptions import BaseServiceException, DomainValidationException


class MemoryExtractionNode:
    def __init__(
        self,
        llm_executor: LLMExecutorPort | None,
        memory_write_service: MemoryWriteService,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.llm_executor = llm_executor
        self.memory_write_service = memory_write_service
        self.tracer = tracer

    async def execute(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        flow_output: dict[str, object] | None,
        config_payload: dict[str, object] | None,
        event_context: MemoryWriteEventContext | None = None,
        trace_id: UUID | None = None,
    ) -> NodeResult:
        summary = MemoryExtractionSummary()
        config = self._resolve_config(config_payload)
        if config is None:
            return NodeResult(
                status=NodeExecutionStatus.SUCCESS,
                payload={"memory_extraction": summary.model_dump(mode="json")},
            )
        if self.llm_executor is None:
            raise DomainValidationException(message="llm_executor_required")
        output_payload = flow_output or {}
        output_keys = sorted(str(key) for key in output_payload.keys())
        output_size_bytes = len(json.dumps(output_payload, ensure_ascii=True).encode("utf-8"))
        with self.tracer.observe(
            as_type="span",
            name="domain.context.memory_extraction.started",
            input={
                "flow_output_keys": output_keys,
                "flow_output_size_bytes": output_size_bytes,
                "flow_run_id": str(flow_run_id),
            },
        ):
            extracted = await self._extract(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
                flow_output=output_payload,
                config=config,
                trace_id=trace_id,
            )
            write_context = event_context or MemoryWriteEventContext(
                session_id=session_id,
                flow_run_id=flow_run_id,
                correlation_id=correlation_id,
            )
            for preference_item in extracted.preferences:
                summary.attempted_preferences += 1
                memory_item = {
                    "schema_id": config.preference_schema_id,
                    "schema_version": 1,
                    "source": "inferred_llm",
                    "rag_config_id": str(config.rag_config_id),
                    "data": {
                        "preference_value": preference_item.preference_value,
                    },
                }
                if preference_item.preference_key is not None:
                    memory_item["data"]["preference_key"] = preference_item.preference_key
                try:
                    write_result = await self.memory_write_service.write_memory_item(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        item=memory_item,
                        event_context=write_context,
                    )
                    if "USER_PREFERENCE" in { # Todo: Use MemoryWriteTarget enum
                        target.value for target in write_result.targets_applied
                    }:
                        summary.applied_preferences += 1
                    else:
                        summary.ignored_preferences += 1
                except BaseServiceException:
                    summary.ignored_preferences += 1

            if isinstance(extracted.profile_patch, dict) and extracted.profile_patch:
                summary.attempted_profile += 1
                profile_memory_item = {
                    "schema_id": config.profile_schema_id,
                    "schema_version": 1,
                    "source": "inferred_llm",
                    "rag_config_id": str(config.rag_config_id),
                    "data": {"profile_patch": extracted.profile_patch},
                }
                try:
                    write_result = await self.memory_write_service.write_memory_item(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        item=profile_memory_item,
                        event_context=write_context,
                    )
                    if "USER_MEMORY_PROFILE" in { # Todo: Use MemoryWriteTarget enum
                        target.value for target in write_result.targets_applied
                    }:
                        summary.applied_profile += 1
                    else:
                        summary.ignored_profile += 1
                except BaseServiceException:
                    summary.ignored_profile += 1

            for vector_item in extracted.vector_memory:
                summary.attempted_vector += 1
                vector_memory_item = {
                    "schema_id": vector_item.schema_id,
                    "schema_version": vector_item.schema_version,
                    "source": "inferred_llm",
                    "rag_config_id": str(config.rag_config_id),
                    "data": vector_item.data,
                }
                try:
                    write_result = await self.memory_write_service.write_memory_item(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        item=vector_memory_item,
                        event_context=write_context,
                    )
                    if "USER_MEMORY_VECTOR" in { # Todo: Use MemoryWriteTarget enum
                        target.value for target in write_result.targets_applied
                    }:
                        summary.applied_vector += 1
                    else:
                        summary.ignored_vector += 1
                except BaseServiceException:
                    summary.ignored_vector += 1

        with self.tracer.observe(
            as_type="event",
            name="domain.context.memory_extraction.completed",
            input={
                "flow_run_id": str(flow_run_id),
                "summary": summary.model_dump(mode="json"),
            },
        ):
            return NodeResult(
                status=NodeExecutionStatus.SUCCESS,
                payload={"memory_extraction": summary.model_dump(mode="json")},
            )

    def _resolve_config(
        self, config_payload: dict[str, object] | None
    ) -> MemoryExtractionConfig | None:
        if not isinstance(config_payload, dict):
            return None
        config = MemoryExtractionConfig.model_validate(config_payload)
        if not config.enabled:
            return None
        return config

    async def _extract(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        session_id: UUID,
        flow_run_id: UUID,
        correlation_id: UUID,
        flow_output: dict[str, object],
        config: MemoryExtractionConfig,
        trace_id: UUID | None,
    ) -> MemoryExtractionLLMOutput:
        output_schema = config.llm.output_schema or {
            "type": "object",
            "properties": {
                "preferences": {"type": "array"},
                "profile_patch": {"type": "object"},
                "vector_memory": {"type": "array"},
            },
            "required": ["preferences", "profile_patch", "vector_memory"],
        }
        llm_request = LLMRequest(
            prompt=self._render_prompt(config.llm.prompt, flow_output),
            input_schema=config.llm.input_schema,
            output_schema=output_schema,
            model_alias=config.llm.model_alias,
            max_tokens=config.llm.max_tokens,
            max_latency_ms=config.llm.max_latency_ms,
            max_cost_usd=config.llm.max_cost_usd,
            retry_limit=config.llm.retry_limit,
            fallback_model_alias=config.llm.fallback_model_alias,
            task_type=LLMTaskType(config.llm.task_type),
            user_id=user_id,
            conversation_key=f"{tenant_id}:{session_id}",
        )
        llm_result = await self.llm_executor.execute_llm(
            request=llm_request,
            trace=TraceContext(
                trace_id=trace_id or flow_run_id,
                flow_run_id=flow_run_id,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
            ),
            tenant_id=tenant_id,
            session_id=session_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            node_id=None,
            provider=config.llm.provider,
            policy_llm={},
        )
        return MemoryExtractionLLMOutput.model_validate(llm_result.output or {})

    def _render_prompt(self, template: str, flow_output: dict[str, object]) -> str:
        return f"{template}\n\nFLOW_OUTPUT_JSON:\n{json.dumps(flow_output, ensure_ascii=True)}"
