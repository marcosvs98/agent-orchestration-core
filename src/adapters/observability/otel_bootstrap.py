from __future__ import annotations

import contextlib
import os
import threading
from logging import NOTSET, Filter, LogRecord, getLogger
from collections.abc import Iterator, Mapping, Sequence
from contextvars import ContextVar
from typing import Dict, Final
from uuid import uuid4

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    Link,
    ParentBased,
    Sampler,
    SamplingResult,
    TraceIdRatioBased,
)
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes

from adapters.observability.otel_attributes import AttributeValue
from settings import (
    APPLICATION_VERSION,
    ENVIRONMENT,
    LOGS_ENABLED,
    METRICS_ENABLED,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_EXPORTER_OTLP_HEADERS,
    OTEL_METRIC_EXPORT_INTERVAL_MS,
    OTEL_SAMPLE_RATIO_DEFAULT,
    OTEL_SAMPLE_RATIO_REPOSITORY,
    OTEL_SERVICE_NAME,
    OTEL_SERVICE_NAMESPACE,
    OTEL_SHUTDOWN_TIMEOUT_MS,
    TRACING_ENABLED,
)

INSTRUMENTATION_SCOPE: Final[str] = "agent-orchestration-core"
REPOSITORY_NAME_MARKER: Final[str] = "repository."
INVALID_TRACE_ID: Final[int] = 0

_BOOTSTRAP_LOCK: Final[threading.Lock] = threading.Lock()
_STATE: Dict[str, object] = {}

_FORCED_TRACE_ID: ContextVar[int | None] = ContextVar("aoc_forced_trace_id", default=None)
_BOUND_ATTRIBUTES: ContextVar[Mapping[str, AttributeValue] | None] = ContextVar(
    "aoc_bound_span_attributes", default=None
)


@contextlib.contextmanager
def force_trace_id(trace_id: int) -> Iterator[None]:
    if trace_id == INVALID_TRACE_ID:
        yield
        return
    token = _FORCED_TRACE_ID.set(trace_id)
    try:
        yield
    finally:
        _FORCED_TRACE_ID.reset(token)


@contextlib.contextmanager
def bind_span_attributes(attributes: Mapping[str, AttributeValue]) -> Iterator[None]:
    if not attributes:
        yield
        return
    current = _BOUND_ATTRIBUTES.get()
    merged: Dict[str, AttributeValue] = dict(current) if current else {}
    merged.update(attributes)
    token = _BOUND_ATTRIBUTES.set(merged)
    try:
        yield
    finally:
        _BOUND_ATTRIBUTES.reset(token)


def bound_span_attributes() -> Mapping[str, AttributeValue]:
    return _BOUND_ATTRIBUTES.get() or {}


class ForcedTraceIdGenerator(RandomIdGenerator):
    def generate_trace_id(self) -> int:
        forced = _FORCED_TRACE_ID.get()
        if forced is not None and forced != INVALID_TRACE_ID:
            return forced
        return super().generate_trace_id()


class ExcludeTelemetrySdkLogs(Filter):
    def filter(self, record: LogRecord) -> bool:
        return not record.name.startswith(("opentelemetry", "urllib3"))


class BoundAttributeSpanProcessor(SpanProcessor):
    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        bound = _BOUND_ATTRIBUTES.get()
        if not bound or not span.is_recording():
            return
        existing = span.attributes or {}
        missing = {key: value for key, value in bound.items() if key not in existing}
        if missing:
            span.set_attributes(missing)


def is_repository_span(name: str) -> bool:
    return REPOSITORY_NAME_MARKER in name


def _ratio_sampler(ratio: float) -> Sampler:
    if ratio >= 1.0:
        return ALWAYS_ON
    if ratio <= 0.0:
        return ALWAYS_OFF
    return TraceIdRatioBased(ratio)


class ObservationSampler(Sampler):
    def __init__(self, *, default_ratio: float, repository_ratio: float) -> None:
        self._default = ParentBased(root=_ratio_sampler(default_ratio))
        self._repository = _ratio_sampler(repository_ratio)
        self._description = (
            f"AocObservationSampler(default={default_ratio},repository={repository_ratio})"
        )

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        delegate = self._repository if is_repository_span(name) else self._default
        return delegate.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )

    def get_description(self) -> str:
        return self._description


def build_sampler() -> Sampler:
    return ObservationSampler(
        default_ratio=OTEL_SAMPLE_RATIO_DEFAULT,
        repository_ratio=OTEL_SAMPLE_RATIO_REPOSITORY,
    )


def parse_otlp_headers(raw: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for pair in raw.split(","):
        candidate = pair.strip()
        if not candidate or "=" not in candidate:
            continue
        key, value = candidate.split("=", 1)
        key = key.strip()
        if key:
            headers[key] = value.strip()
    return headers


def signal_endpoint(base: str, signal: str) -> str:
    normalized = base.rstrip("/")
    suffix = f"/v1/{signal}"
    if normalized.endswith(suffix):
        return normalized
    return f"{normalized}{suffix}"


def build_resource(*, component: str, instance_id: str) -> Resource:
    return Resource.create(
        {
            "service.name": OTEL_SERVICE_NAME,
            "service.namespace": OTEL_SERVICE_NAMESPACE,
            "service.version": APPLICATION_VERSION,
            "service.instance.id": instance_id,
            "deployment.environment.name": ENVIRONMENT,
            "aoc.component": component,
        }
    )


def default_instance_id() -> str:
    return f"{os.uname().nodename}-{os.getpid()}-{uuid4().hex[:8]}"


def bootstrap_telemetry(*, component: str, instance_id: str | None = None) -> None:
    with _BOOTSTRAP_LOCK:
        if _STATE.get("bootstrapped"):
            return
        _STATE["bootstrapped"] = True
        set_global_textmap(TraceContextTextMapPropagator())
        if not TRACING_ENABLED and not METRICS_ENABLED and not LOGS_ENABLED:
            return
        resource = build_resource(
            component=component, instance_id=instance_id or default_instance_id()
        )
        headers = parse_otlp_headers(OTEL_EXPORTER_OTLP_HEADERS)
        if TRACING_ENABLED:
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=build_sampler(),
                id_generator=ForcedTraceIdGenerator(),
            )
            tracer_provider.add_span_processor(BoundAttributeSpanProcessor())
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=signal_endpoint(OTEL_EXPORTER_OTLP_ENDPOINT, "traces"),
                        headers=headers or None,
                    )
                )
            )
            trace.set_tracer_provider(tracer_provider)
            _STATE["tracer_provider"] = tracer_provider
        if METRICS_ENABLED:
            reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=signal_endpoint(OTEL_EXPORTER_OTLP_ENDPOINT, "metrics"),
                    headers=headers or None,
                ),
                export_interval_millis=OTEL_METRIC_EXPORT_INTERVAL_MS,
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(meter_provider)
            _STATE["meter_provider"] = meter_provider
        if LOGS_ENABLED:
            logger_provider = LoggerProvider(resource=resource)
            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(
                    OTLPLogExporter(
                        endpoint=signal_endpoint(OTEL_EXPORTER_OTLP_ENDPOINT, "logs"),
                        headers=headers or None,
                    )
                )
            )
            set_logger_provider(logger_provider)
            handler = LoggingHandler(level=NOTSET, logger_provider=logger_provider)
            handler.addFilter(ExcludeTelemetrySdkLogs())
            getLogger().addHandler(handler)
            _STATE["logger_provider"] = logger_provider
            _STATE["log_handler"] = handler


def flush_telemetry(timeout_millis: int) -> None:
    tracer_provider = _STATE.get("tracer_provider")
    if isinstance(tracer_provider, TracerProvider):
        tracer_provider.force_flush(timeout_millis)
    meter_provider = _STATE.get("meter_provider")
    if isinstance(meter_provider, MeterProvider):
        meter_provider.force_flush(timeout_millis)
    logger_provider = _STATE.get("logger_provider")
    if isinstance(logger_provider, LoggerProvider):
        logger_provider.force_flush(timeout_millis)


def shutdown_telemetry() -> None:
    with _BOOTSTRAP_LOCK:
        tracer_provider = _STATE.pop("tracer_provider", None)
        meter_provider = _STATE.pop("meter_provider", None)
        logger_provider = _STATE.pop("logger_provider", None)
        handler = _STATE.pop("log_handler", None)
        _STATE.pop("bootstrapped", None)
    if isinstance(handler, LoggingHandler):
        getLogger().removeHandler(handler)
    if isinstance(tracer_provider, TracerProvider):
        tracer_provider.force_flush(OTEL_SHUTDOWN_TIMEOUT_MS)
        tracer_provider.shutdown()
    if isinstance(meter_provider, MeterProvider):
        meter_provider.force_flush(OTEL_SHUTDOWN_TIMEOUT_MS)
        meter_provider.shutdown(OTEL_SHUTDOWN_TIMEOUT_MS)
    if isinstance(logger_provider, LoggerProvider):
        logger_provider.force_flush(OTEL_SHUTDOWN_TIMEOUT_MS)
        logger_provider.shutdown()
