from __future__ import annotations

from typing import Iterator, Protocol, Dict, Any
from uuid import UUID

from domain.execution.schemas.trace import TraceContext


class ObservationHandle(Protocol):
    def update(self, **kwargs: Any) -> None: ...
    def success(
        self,
        *,
        output: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None: ...
    def error(
        self,
        *,
        error_type: str,
        error_message: str,
        output: Dict[str, Any] | None = None,
        metadata: Dict[str, Any] | None = None,
        level: str = "ERROR",
        status_message: str | None = None,
        **kwargs: Any,
    ) -> None: ...


class RuntimeTracerPort(Protocol):
    def start_flow_trace(
        self,
        *,
        flow_run_id: UUID,
        flow_id: UUID,
        flow_version_id: UUID,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: str | None,
        external_request_id: str | None = None,
        trace_id: UUID | None = None,
        interaction_id: UUID | None = None,
        correlation_id: UUID | None = None,
        channel: str | None = None,
        external_message_id: str | None = None,
        graph_snapshot_id: UUID | None = None,
        execution_plan_hash: str | None = None,
        flow_name: str | None = None,
    ) -> TraceContext: ...

    def flow(
        self, *, trace: TraceContext, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[ObservationHandle]: ...

    def observe(
        self,
        *,
        as_type: str,
        name: str,
        input: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Iterator[ObservationHandle]: ...

    def flush(self) -> None: ...

    def shutdown(self) -> None: ...
