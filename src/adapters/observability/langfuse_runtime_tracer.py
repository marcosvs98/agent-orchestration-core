from __future__ import annotations

import contextlib
from typing import Any, Dict, Iterator
from uuid import UUID

import structlog
from adapters.observability.logging import get_logger
from domain.execution.schemas.trace import TraceContext
from exceptions.service_exceptions import DomainValidationException
from langfuse import Langfuse, propagate_attributes
from settings import (
    APPLICATION_VERSION,
    ENVIRONMENT,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)

logger = get_logger(__name__)


def _get_contextvars_metadata() -> Dict[str, Any]:
    try:
        return structlog.contextvars.get_contextvars()
    except Exception:
        return {}


def _merge_metadata(base_metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    metadata = dict(base_metadata) if base_metadata else {}
    contextvars_metadata = _get_contextvars_metadata()
    if contextvars_metadata:
        metadata.update(contextvars_metadata)
    return metadata


class ObservationHandle:
    def __init__(self, observation: Any) -> None:
        self.observation = observation

    def update(self, **kwargs: Any) -> None:
        if self.observation is None:
            return
        try:
            self.observation.update(**kwargs)
        except Exception as e:
            logger.error(
                "Failed to update Langfuse observation",
                error=str(e),
                error_type=type(e).__name__,
            )

    def success(
        self,
        *,
        output: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        update_data: Dict[str, Any] = {"output": output, "level": "INFO"}
        if metadata:
            update_data["metadata"] = _merge_metadata(metadata)
        update_data.update(kwargs)
        self.update(**update_data)

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
    ) -> None:
        update_data: Dict[str, Any] = {
            "level": level,
            "status_message": status_message or error_message,
            "output": output
            if output is not None
            else {
                "status": "error",
                "error_type": error_type,
                "error_message": error_message,
            },
        }
        if metadata:
            update_data["metadata"] = _merge_metadata(metadata)
        update_data.update(kwargs)
        self.update(**update_data)


class LangfuseRuntimeTracer:
    def __init__(
        self, *, environment: str | None = None, runtime_version: str | None = None
    ) -> None:
        if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY or not LANGFUSE_HOST:
            raise DomainValidationException(message="langfuse_not_configured")
        self.environment = environment or ENVIRONMENT
        self.runtime_version = runtime_version or APPLICATION_VERSION
        try:
            self.langfuse = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Langfuse client",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise DomainValidationException(
                message="langfuse_initialization_failed"
            ) from e

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
    ) -> TraceContext:
        try:
            if external_request_id:
                deterministic_trace_id = self.langfuse.create_trace_id(
                    seed=external_request_id
                )
                trace_id_val = UUID(deterministic_trace_id)
            else:
                trace_id_val = trace_id or flow_run_id

            trace_context = TraceContext(
                trace_id=trace_id_val,
                flow_run_id=flow_run_id,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                root_observation_id=None,
                flow_name=flow_name,
                flow_id=flow_id,
                flow_version_id=flow_version_id,
                interaction_id=interaction_id,
                correlation_id=correlation_id,
                channel=channel,
                external_message_id=external_message_id,
                graph_snapshot_id=graph_snapshot_id,
                execution_plan_hash=execution_plan_hash,
            )
            return trace_context
        except Exception:
            logger.exception("Failed to start flow trace", flow_run_id=str(flow_run_id))
            trace_id_val = trace_id or flow_run_id
            return TraceContext(
                trace_id=trace_id_val,
                flow_run_id=flow_run_id,
                tenant_id=tenant_id,
                session_id=session_id,
                user_id=user_id,
                root_observation_id=None,
            )

    @contextlib.contextmanager
    def flow(
        self, *, trace: TraceContext, input: Dict[str, Any], name: str | None = None
    ) -> Iterator[ObservationHandle]:
        span_name = name or trace.flow_name or "flow.run"
        if trace.user_id is None:
            trace.user_id = str(trace.tenant_id)
        propagate_metadata: Dict[str, Any] = {
            "tenant_id": str(trace.tenant_id),
            "flow_run_id": str(trace.flow_run_id),
            "trace_id": str(trace.trace_id),
        }
        if trace.flow_id:
            propagate_metadata["flow_id"] = str(trace.flow_id)
        if trace.flow_version_id:
            propagate_metadata["flow_version_id"] = str(trace.flow_version_id)
            propagate_metadata["flow_version"] = str(trace.flow_version_id)
        if trace.interaction_id:
            propagate_metadata["interaction_id"] = str(trace.interaction_id)
        if trace.correlation_id:
            propagate_metadata["correlation_id"] = str(trace.correlation_id)
        if trace.channel:
            propagate_metadata["channel"] = trace.channel
        if trace.external_message_id:
            propagate_metadata["external_message_id"] = trace.external_message_id
        if trace.graph_snapshot_id:
            propagate_metadata["graph_snapshot_id"] = str(trace.graph_snapshot_id)
        if trace.execution_plan_hash:
            propagate_metadata["execution_plan_hash"] = trace.execution_plan_hash
        if trace.flow_name:
            propagate_metadata["flow_name"] = trace.flow_name
        if self.environment:
            propagate_metadata["environment"] = self.environment
        if self.runtime_version:
            propagate_metadata["runtime_version"] = self.runtime_version

        flow_span = None
        handle = ObservationHandle(None)
        try:
            with self.langfuse.start_as_current_observation(
                as_type="span",
                name=span_name,
                trace_context={"trace_id": trace.trace_id.hex},
                input=input,
                metadata=_merge_metadata(
                    {"flow_name": trace.flow_name} if trace.flow_name else None
                ),
            ) as flow_span:
                handle = ObservationHandle(flow_span)
                root_observation_id = getattr(flow_span, "id", None) or getattr(
                    flow_span, "observation_id", None
                )
                if root_observation_id and not trace.root_observation_id:
                    trace.root_observation_id = root_observation_id
                with propagate_attributes(
                    user_id=trace.user_id,
                    session_id=str(trace.session_id) if trace.session_id else None,
                    metadata=propagate_metadata,
                    version=str(trace.flow_version_id)
                    if trace.flow_version_id
                    else None,
                ):
                    yield handle
        except Exception as e:
            if flow_span is not None:
                handle.error(error_type=type(e).__name__, error_message=str(e))
            logger.exception(
                "Failed to start flow span in Langfuse",
                error_type=type(e).__name__,
                trace_id=str(trace.trace_id),
            )
            raise

    @contextlib.contextmanager
    def observe(
        self,
        *,
        as_type: str,
        name: str,
        input: Dict[str, Any],
        metadata: Dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Iterator[ObservationHandle]:
        handle = ObservationHandle(None)
        try:
            if as_type == "event":
                self.langfuse.create_event(
                    name=name,
                    input=input,
                    metadata=_merge_metadata(metadata),
                )
                yield handle
                return
            with self.langfuse.start_as_current_observation(
                as_type=as_type,
                name=name,
                input=input,
                metadata=_merge_metadata(metadata),
                **kwargs,
            ) as observation:
                handle = ObservationHandle(observation)
                yield handle
        except Exception as e:
            if handle.observation is not None:
                handle.error(error_type=type(e).__name__, error_message=str(e))
            logger.exception(
                "Failed to start Langfuse observation",
                error_type=type(e).__name__,
                observation_type=as_type,
                observation_name=name,
            )
            raise

    def flush(self) -> None:
        try:
            self.langfuse.flush()
        except Exception as e:
            logger.exception(
                "Failed to flush Langfuse events",
                error_type=type(e).__name__,
            )

    def shutdown(self) -> None:
        try:
            self.langfuse.shutdown()
        except Exception as e:
            logger.exception(
                "Failed to shutdown Langfuse client",
                error_type=type(e).__name__,
            )
