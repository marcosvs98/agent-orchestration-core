from __future__ import annotations

from datetime import datetime
from typing import Iterator, Protocol, Dict, Any
from uuid import UUID

from domain.execution.schemas.trace import TraceContext
from domain.execution.schemas.events import ExecutionEventType


class LLMGenerationHandle(Protocol):
    def update_success(
        self,
        *,
        output: dict,
        token_usage: dict,
        cost: float,
        latency_ms: int,
        model_version: str,
        input_data: dict | None = None,
        model_parameters: dict | None = None,
        completion_start_time: datetime | None = None,
    ) -> None:
        ...

    def update_failure(
        self,
        *,
        error_type: str,
        error_message: str,
        input_data: dict | None = None,
        traceback_str: str | None = None,
    ) -> None:
        ...


class GuardrailSpanHandle(Protocol):
    def update_decision(
        self,
        *,
        decision: str,
        reason_code: str,
        applied_limits: dict,
        overrides: dict | None = None,
    ) -> None:
        ...


class RetrieverSpanHandle(Protocol):
    def update(
        self,
        *,
        input: Dict[str, Any] | None = None,
        output: Dict[str, Any] | None = None,
        usage_details: Dict[str, Any] | None = None,
    ) -> None:
        ...

    def update_results(
        self,
        *,
        chunks: list,
        top_k: int,
        similarity_scores: list[float],
        usage_details: Dict[str, Any] | None = None,
    ) -> None:
        ...


class EvaluatorSpanHandle(Protocol):
    def update_result(
        self, *, passed: bool, errors: list[str] | None = None, score: float | None = None
    ) -> None:
        ...


class EmbeddingSpanHandle(Protocol):
    def update_success(
        self,
        *,
        embedding: list[float],
        dimension: int,
        latency_ms: int,
        usage_details: Dict[str, Any] | None = None,
    ) -> None:
        ...

    def update_failure(self, *, error_type: str, error_message: str) -> None:
        ...


class RuntimeTracerPort(Protocol):
    def start_flow_trace(
        self,
        *,
        flow_run_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: UUID | None,
        external_request_id: str | None = None,
        trace_id: UUID | None = None,
    ) -> TraceContext:
        ...

    def end_flow_trace(self, *, output: dict | None = None) -> None:
        ...

    def start_flow_span(self, *, trace: TraceContext, name: str | None = None) -> Iterator[None]:
        ...

    def start_node_span(
        self, *, node_id: str, node_type: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[None]:
        ...

    def start_guardrail_span(
        self, *, guardrail_type: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[GuardrailSpanHandle]:
        ...

    def start_tool_span(self, *, tool_id: str, input: Dict[str, Any], name: str | None = None) -> Iterator[None]:
        ...

    def start_llm_generation(
        self,
        *,
        model_id: str,
        task_type: str,
        input: Dict[str, Any],
        prompt_version: int | None = None,
        prompt_frozen_hash: str | None = None,
        node_type: str | None = None,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        tenant_id: UUID | None = None,
        name: str | None = None,
    ) -> Iterator[LLMGenerationHandle]:
        ...

    def start_chain_span(
        self, *, chain_name: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[None]:
        ...

    def start_retriever_span(
        self,
        *,
        retriever_name: str,
        query: str | None = None,
        input: Dict[str, Any] | None = None,
        name: str | None = None,
    ) -> Iterator[RetrieverSpanHandle]:
        ...

    def start_evaluator_span(
        self, *, evaluator_name: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[EvaluatorSpanHandle]:
        ...

    def start_embedding_span(
        self, *, model_id: str, input_text: str, name: str | None = None
    ) -> Iterator[EmbeddingSpanHandle]:
        ...

    def start_agent_span(
        self, *, agent_name: str, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[None]:
        ...

    def create_event(
        self, *, event_type: ExecutionEventType, input: Dict[str, Any] | None = None
    ) -> None:
        ...

    def flush(self) -> None:
        ...

    def shutdown(self) -> None:
        ...
