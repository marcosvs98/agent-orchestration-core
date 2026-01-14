from __future__ import annotations

import contextlib
from typing import Any, Dict, Iterator
from uuid import UUID, uuid4

from domain.execution.schemas.trace import TraceContext
from exceptions.service_exceptions import DomainValidationException
from settings import (
    APPLICATION_VERSION,
    ENVIRONMENT,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)


class LLMGenerationHandle:
    def __init__(self) -> None:
        self.updated = False

    def update_success(
        self,
        *,
        output: dict,
        token_usage: dict,
        cost: float,
        latency_ms: int,
        model_version: str,
    ) -> None:
        self.updated = True
        # No-op placeholder for Langfuse SDK integration

    def update_failure(self, *, error_type: str, error_message: str) -> None:
        self.updated = True
        # No-op placeholder for Langfuse SDK integration


class LangfuseRuntimeTracer:
    """Single entry point for Langfuse integration. Blocks execution if misconfigured."""

    def __init__(self, *, environment: str | None = None, runtime_version: str | None = None) -> None:
        if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY or not LANGFUSE_HOST:
            raise DomainValidationException(message="langfuse_not_configured")
        self.environment = environment or ENVIRONMENT
        self.runtime_version = runtime_version or APPLICATION_VERSION

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
        trace_id_val = str(trace_id or flow_run_id)
        root_observation_id = str(uuid4())
        return TraceContext(
            trace_id=UUID(trace_id_val),
            flow_run_id=flow_run_id,
            tenant_id=tenant_id,
            root_observation_id=root_observation_id,
        )

    def end_flow_trace(self, *, output: dict | None = None) -> None:
        return None

    @contextlib.contextmanager
    def start_flow_span(self, *, trace: TraceContext) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def start_node_span(self, *, node_id: str, node_type: str, input: Dict[str, Any]) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def start_guardrail_span(self, *, guardrail_type: str, input: Dict[str, Any]) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def start_tool_span(self, *, tool_id: str, input: Dict[str, Any]) -> Iterator[None]:
        yield

    @contextlib.contextmanager
    def start_llm_generation(self, *, model_id: str, task_type: str, input: Dict[str, Any]) -> Iterator[LLMGenerationHandle]:
        handle = LLMGenerationHandle()
        yield handle

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None
