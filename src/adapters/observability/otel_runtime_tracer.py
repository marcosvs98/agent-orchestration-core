from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Iterator, Mapping
from typing import Any, Dict, Final
from uuid import UUID, uuid4

from opentelemetry import metrics
from opentelemetry import trace as otel_trace
from opentelemetry.context import Context
from opentelemetry.trace import (
    INVALID_SPAN_ID,
    Link,
    NonRecordingSpan,
    Span,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    TraceFlags,
    set_span_in_context,
)

from adapters.observability.logging import get_logger
from adapters.observability.otel_attributes import (
    EXCEPTION_MESSAGE,
    EXCEPTION_TYPE,
    GEN_AI_COST_USD,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    OBSERVATION_INPUT,
    OBSERVATION_LEVEL,
    OBSERVATION_OUTPUT,
    OBSERVATION_TYPE,
    OBSERVATION_VERSION,
    TENANT_ID,
    AttributeValue,
    context_attributes,
    cost_attributes,
    json_attribute,
    model_parameter_attributes,
    sanitize_attributes,
    to_attribute_value,
    usage_attributes,
)
from adapters.observability.otel_bootstrap import (
    INSTRUMENTATION_SCOPE,
    bind_span_attributes,
    bound_span_attributes,
    flush_telemetry,
    force_trace_id,
    shutdown_telemetry,
)
from domain.execution.schemas.trace import ConversationTraceContext, TraceContext
from settings import (
    APPLICATION_VERSION,
    ENVIRONMENT,
    METRICS_ENABLED,
    OTEL_CAPTURE_CONTENT,
    OTEL_FLUSH_TIMEOUT_MS,
    TRACING_ENABLED,
)

logger = get_logger()

GENERATION_TYPES: Final[frozenset[str]] = frozenset({"generation", "embedding"})
CLIENT_SPAN_TYPES: Final[frozenset[str]] = frozenset(
    {"generation", "embedding", "retriever", "tool"}
)
SPAN_KIND_BY_TYPE: Final[Dict[str, SpanKind]] = {
    observation_type: SpanKind.CLIENT for observation_type in CLIENT_SPAN_TYPES
}
EVENT_TYPE: Final[str] = "event"
GEN_AI_OPERATION_BY_TYPE: Final[Dict[str, str]] = {
    "generation": "chat",
    "embedding": "embeddings",
}
PROVIDER_METADATA_KEYS: Final[tuple[str, ...]] = ("provider", "provider_name", "llm_provider")
MODEL_METADATA_KEYS: Final[tuple[str, ...]] = ("provider_model", "model_alias", "model_used")


def deterministic_trace_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).digest()[:16].hex()


def _gen_ai_aliases(attributes: Mapping[str, AttributeValue]) -> Dict[str, AttributeValue]:
    aliases: Dict[str, AttributeValue] = {}
    if GEN_AI_PROVIDER_NAME not in attributes:
        for key in PROVIDER_METADATA_KEYS:
            value = attributes.get(key)
            if value is not None:
                aliases[GEN_AI_PROVIDER_NAME] = value
                break
    if GEN_AI_REQUEST_MODEL not in attributes:
        for key in MODEL_METADATA_KEYS:
            value = attributes.get(key)
            if value is not None:
                aliases[GEN_AI_REQUEST_MODEL] = value
                break
    return aliases


def _content_attribute(key: str, value: Any) -> Dict[str, AttributeValue]:
    if not OTEL_CAPTURE_CONTENT:
        return {}
    encoded = json_attribute(value)
    if encoded is None:
        return {}
    return {key: encoded}


class _UsageRecorder:
    def __init__(self) -> None:
        self._enabled = bool(METRICS_ENABLED)
        meter = metrics.get_meter(INSTRUMENTATION_SCOPE, APPLICATION_VERSION)
        self._tokens = meter.create_histogram(
            name="gen_ai.client.token.usage",
            unit="{token}",
            description="Tokens consumed per model call",
        )
        self._cost = meter.create_counter(
            name="aoc.gen_ai.cost.usd",
            unit="USD",
            description="Model spend attributed to a call",
        )

    def record(
        self,
        *,
        span_attributes: Mapping[str, AttributeValue],
        usage: Mapping[str, AttributeValue],
        cost: Mapping[str, AttributeValue],
    ) -> None:
        if not self._enabled:
            return
        labels: Dict[str, AttributeValue] = {}
        for key in (GEN_AI_REQUEST_MODEL, GEN_AI_OPERATION_NAME, GEN_AI_PROVIDER_NAME, TENANT_ID):
            value = span_attributes.get(key)
            if value is not None:
                labels[key] = value
        input_tokens = usage.get(GEN_AI_USAGE_INPUT_TOKENS)
        if isinstance(input_tokens, int):
            self._tokens.record(input_tokens, attributes={**labels, "gen_ai.token.type": "input"})
        output_tokens = usage.get(GEN_AI_USAGE_OUTPUT_TOKENS)
        if isinstance(output_tokens, int):
            self._tokens.record(output_tokens, attributes={**labels, "gen_ai.token.type": "output"})
        cost_usd = cost.get(GEN_AI_COST_USD)
        if isinstance(cost_usd, (int, float)):
            self._cost.add(float(cost_usd), attributes=labels)


SCOPE_ATTRIBUTE_KEYS: Final[tuple[str, ...]] = ("tenant_id", "agent_run_id", "flow_run_id")


def _scope_attributes(attributes: Mapping[str, AttributeValue]) -> Dict[str, AttributeValue]:
    scoped: Dict[str, AttributeValue] = {}
    for key in SCOPE_ATTRIBUTE_KEYS:
        value = attributes.get(key)
        if value is not None:
            scoped[key] = value
    return scoped


class ObservationHandle:
    def __init__(
        self,
        span: Span | None,
        usage_recorder: _UsageRecorder | None = None,
        initial_attributes: Mapping[str, AttributeValue] | None = None,
    ) -> None:
        self.span = span
        self._usage_recorder = usage_recorder
        self._attributes: Dict[str, AttributeValue] = dict(initial_attributes or {})
        self._failed = False
        self._ended = False

    def update(self, **kwargs: Any) -> None:
        if self.span is None:
            return
        try:
            self._apply(kwargs)
        except Exception as e:
            logger.warning(
                "otel_observation_update_failed",
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
        payload: Dict[str, Any] = {"output": output}
        if metadata:
            payload["metadata"] = metadata
        payload.update(kwargs)
        self.update(**payload)

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
        payload: Dict[str, Any] = {
            "level": level,
            "status_message": status_message or error_message,
            EXCEPTION_TYPE: error_type,
            EXCEPTION_MESSAGE: error_message,
        }
        if output is not None:
            payload["output"] = output
        if metadata:
            payload["metadata"] = metadata
        payload.update(kwargs)
        self._failed = True
        self.update(**payload)

    def record_exception(self, exc: BaseException) -> None:
        if self.span is None:
            return
        self._failed = True
        try:
            self.span.record_exception(exc)
            self.span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            self._set({EXCEPTION_TYPE: type(exc).__name__, EXCEPTION_MESSAGE: str(exc)})
        except Exception:
            return

    def finalize(self) -> None:
        if self.span is None or self._ended:
            return
        self._ended = True
        try:
            if not self._failed:
                self.span.set_status(Status(StatusCode.OK))
            self.span.end()
        except Exception as e:
            logger.warning(
                "otel_observation_finalize_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

    def _set(self, attributes: Mapping[str, AttributeValue]) -> None:
        if self.span is None or not attributes:
            return
        self._attributes.update(attributes)
        self.span.set_attributes(dict(attributes))

    def _apply(self, kwargs: Dict[str, Any]) -> None:
        attributes: Dict[str, AttributeValue] = {}

        if "output" in kwargs:
            attributes.update(self._output_attributes(kwargs.pop("output")))
        if "input" in kwargs:
            attributes.update(self._input_attributes(kwargs.pop("input")))
        metadata = kwargs.pop("metadata", None)
        if metadata:
            attributes.update(sanitize_attributes(metadata))

        model = kwargs.pop("model", None)
        if model is not None:
            model_value = to_attribute_value(model)
            if model_value is not None:
                key = (
                    GEN_AI_RESPONSE_MODEL
                    if GEN_AI_REQUEST_MODEL in self._attributes
                    else GEN_AI_REQUEST_MODEL
                )
                attributes[key] = model_value

        attributes.update(model_parameter_attributes(kwargs.pop("model_parameters", None)))

        usage = usage_attributes(kwargs.pop("usage_details", None))
        cost = cost_attributes(kwargs.pop("cost_details", None))
        attributes.update(usage)
        attributes.update(cost)

        version = kwargs.pop("version", None)
        if version is not None:
            version_value = to_attribute_value(version)
            if version_value is not None:
                attributes[OBSERVATION_VERSION] = version_value

        level = kwargs.pop("level", None)
        status_message = kwargs.pop("status_message", None)
        kwargs.pop("completion_start_time", None)
        kwargs.pop("prompt", None)

        for key, raw in kwargs.items():
            converted = to_attribute_value(raw)
            if converted is None:
                continue
            attributes[
                key if key.startswith(("aoc.", "gen_ai.", "exception.")) else f"aoc.{key}"
            ] = converted

        if level is not None:
            level_value = to_attribute_value(level)
            if level_value is not None:
                attributes[OBSERVATION_LEVEL] = level_value

        if self._attributes.get(OBSERVATION_TYPE) in GENERATION_TYPES:
            attributes.update(_gen_ai_aliases({**self._attributes, **attributes}))

        self._set(attributes)

        if self._failed and self.span is not None:
            self.span.set_status(
                Status(StatusCode.ERROR, str(status_message) if status_message else None)
            )
        elif status_message is not None:
            self._set({"aoc.observation.status_message": to_attribute_value(status_message) or ""})

        if usage or cost:
            self._record_usage(usage, cost)

    def _record_usage(
        self, usage: Mapping[str, AttributeValue], cost: Mapping[str, AttributeValue]
    ) -> None:
        if self._usage_recorder is None:
            return
        merged: Dict[str, AttributeValue] = dict(bound_span_attributes())
        merged.update(self._attributes)
        self._usage_recorder.record(span_attributes=merged, usage=usage, cost=cost)

    def _input_attributes(self, value: Any) -> Dict[str, AttributeValue]:
        key = (
            GEN_AI_INPUT_MESSAGES
            if self._attributes.get(OBSERVATION_TYPE) in GENERATION_TYPES
            else OBSERVATION_INPUT
        )
        return _content_attribute(key, value)

    def _output_attributes(self, value: Any) -> Dict[str, AttributeValue]:
        key = (
            GEN_AI_OUTPUT_MESSAGES
            if self._attributes.get(OBSERVATION_TYPE) in GENERATION_TYPES
            else OBSERVATION_OUTPUT
        )
        return _content_attribute(key, value)


NULL_HANDLE: Final[ObservationHandle] = ObservationHandle(None)


class OtelRuntimeTracer:
    def __init__(
        self, *, environment: str | None = None, runtime_version: str | None = None
    ) -> None:
        self._enabled = bool(TRACING_ENABLED)
        self.environment = environment or ENVIRONMENT
        self.runtime_version = runtime_version or APPLICATION_VERSION
        self._tracer = otel_trace.get_tracer(INSTRUMENTATION_SCOPE, self.runtime_version)
        self._usage_recorder = _UsageRecorder()

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
        return TraceContext(
            trace_id=self._resolve_trace_id(
                trace_id=trace_id, external_request_id=external_request_id, fallback=flow_run_id
            ),
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

    def start_conversation_trace(
        self,
        *,
        tenant_id: UUID,
        session_id: UUID | None,
        user_id: str | None,
        correlation_id: UUID | None = None,
        trace_id: UUID | None = None,
        agent_id: UUID | None = None,
        channel: str | None = None,
        external_message_id: str | None = None,
        external_request_id: str | None = None,
        interaction_id: UUID | None = None,
    ) -> ConversationTraceContext:
        return ConversationTraceContext(
            trace_id=self._resolve_trace_id(
                trace_id=trace_id, external_request_id=external_request_id, fallback=uuid4()
            ),
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
            correlation_id=correlation_id,
            agent_id=agent_id,
            channel=channel,
            external_message_id=external_message_id,
            interaction_id=interaction_id,
            root_observation_id=None,
        )

    @contextlib.contextmanager
    def flow(
        self, *, trace: TraceContext, name: str | None = None, **kwargs: Any
    ) -> Iterator[ObservationHandle]:
        span_name = f"flow:{name or trace.flow_name or 'flow.run'}"
        attributes = self._flow_attributes(trace)
        with self._root_observation(
            span_name=span_name,
            trace_id=trace.trace_id,
            attributes=attributes,
            observation_type="span",
            payload=kwargs,
        ) as handle:
            self._assign_root_observation_id(trace, handle)
            with bind_span_attributes(attributes):
                yield handle

    @contextlib.contextmanager
    def conversation(
        self,
        *,
        trace: ConversationTraceContext,
        name: str | None = None,
        **kwargs: Any,
    ) -> Iterator[ObservationHandle]:
        span_name = name or "conversation.turn"
        attributes = self._conversation_attributes(trace)
        with self._root_observation(
            span_name=span_name,
            trace_id=trace.trace_id,
            attributes=attributes,
            observation_type="span",
            payload=kwargs,
        ) as handle:
            self._assign_root_observation_id(trace, handle)
            with bind_span_attributes(attributes):
                yield handle

    @contextlib.contextmanager
    def observe(
        self,
        *,
        as_type: str,
        name: str,
        metadata: Dict[str, Any] | None = None,
        trace_context: Dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Iterator[ObservationHandle]:
        if not self._enabled:
            yield NULL_HANDLE
            return
        attributes = self._observation_attributes(as_type=as_type, metadata=metadata)
        if as_type == EVENT_TYPE:
            self._record_event(name=name, attributes=attributes, payload=kwargs)
            yield NULL_HANDLE
            return
        parent, forced_trace_id, links = self._parent_from_trace_context(trace_context)
        with self._span(
            span_name=name,
            observation_type=as_type,
            attributes=attributes,
            parent=parent,
            forced_trace_id=forced_trace_id,
            links=links,
            payload=kwargs,
        ) as handle:
            with bind_span_attributes(_scope_attributes(attributes)):
                yield handle

    def flush(self) -> None:
        if not self._enabled:
            return
        try:
            flush_telemetry(OTEL_FLUSH_TIMEOUT_MS)
        except Exception as e:
            logger.warning("otel_flush_failed", error=str(e), error_type=type(e).__name__)

    def shutdown(self) -> None:
        try:
            shutdown_telemetry()
        except Exception as e:
            logger.warning("otel_shutdown_failed", error=str(e), error_type=type(e).__name__)

    def _resolve_trace_id(
        self, *, trace_id: UUID | None, external_request_id: str | None, fallback: UUID
    ) -> UUID:
        if trace_id is not None:
            return trace_id
        if external_request_id:
            try:
                return UUID(deterministic_trace_id(external_request_id))
            except ValueError:
                return fallback
        return fallback

    def _flow_attributes(self, trace: TraceContext) -> Dict[str, AttributeValue]:
        raw: Dict[str, Any] = {
            "tenant_id": trace.tenant_id,
            "flow_run_id": trace.flow_run_id,
            "trace_id": trace.trace_id,
            "user_id": trace.user_id,
            "session_id": trace.session_id,
            "flow_id": trace.flow_id,
            "flow_version_id": trace.flow_version_id,
            "interaction_id": trace.interaction_id,
            "correlation_id": trace.correlation_id,
            "channel": trace.channel,
            "external_message_id": trace.external_message_id,
            "graph_snapshot_id": trace.graph_snapshot_id,
            "execution_plan_hash": trace.execution_plan_hash,
            "flow_name": trace.flow_name,
            "env": self.environment,
            "runtime_version": self.runtime_version,
            OBSERVATION_TYPE: "flow",
        }
        return {**context_attributes(), **sanitize_attributes(raw)}

    def _conversation_attributes(
        self, trace: ConversationTraceContext
    ) -> Dict[str, AttributeValue]:
        raw: Dict[str, Any] = {
            "tenant_id": trace.tenant_id,
            "trace_id": trace.trace_id,
            "user_id": trace.user_id,
            "session_id": trace.session_id,
            "correlation_id": trace.correlation_id,
            "agent_id": trace.agent_id,
            "channel": trace.channel,
            "external_message_id": trace.external_message_id,
            "interaction_id": trace.interaction_id,
            "env": self.environment,
            "runtime_version": self.runtime_version,
            OBSERVATION_TYPE: "conversation",
        }
        return {**context_attributes(), **sanitize_attributes(raw)}

    def _observation_attributes(
        self, *, as_type: str, metadata: Dict[str, Any] | None
    ) -> Dict[str, AttributeValue]:
        attributes: Dict[str, AttributeValue] = {}
        attributes.update(context_attributes())
        attributes.update(sanitize_attributes(metadata))
        attributes[OBSERVATION_TYPE] = as_type
        if as_type in GENERATION_TYPES:
            attributes[GEN_AI_OPERATION_NAME] = GEN_AI_OPERATION_BY_TYPE[as_type]
            attributes.update(_gen_ai_aliases(attributes))
        return attributes

    def _record_event(
        self, *, name: str, attributes: Dict[str, AttributeValue], payload: Dict[str, Any]
    ) -> None:
        current = otel_trace.get_current_span()
        if not current.is_recording():
            return
        event_attributes = dict(attributes)
        event_attributes.update(_content_attribute(OBSERVATION_INPUT, payload.get("input")))
        try:
            current.add_event(name, attributes=event_attributes)
        except Exception as e:
            logger.warning("otel_event_failed", error=str(e), error_type=type(e).__name__)

    def _parent_from_trace_context(
        self, trace_context: Dict[str, str] | None
    ) -> tuple[Context | None, int | None, list[Link]]:
        if not trace_context:
            return None, None, []
        raw_trace_id = trace_context.get("trace_id")
        if not raw_trace_id:
            return None, None, []
        try:
            trace_id_int = int(str(raw_trace_id).replace("-", ""), 16)
        except ValueError:
            return None, None, []
        if trace_id_int == 0:
            return None, None, []
        raw_parent = trace_context.get("parent_span_id")
        parent_span_id = INVALID_SPAN_ID
        if raw_parent:
            try:
                parent_span_id = int(str(raw_parent).replace("-", ""), 16)
            except ValueError:
                parent_span_id = INVALID_SPAN_ID
        if parent_span_id != INVALID_SPAN_ID:
            remote_context = SpanContext(
                trace_id=trace_id_int,
                span_id=parent_span_id,
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
            return set_span_in_context(NonRecordingSpan(remote_context)), None, []
        return Context(), trace_id_int, self._ambient_links()

    def _ambient_links(self) -> list[Link]:
        ambient = otel_trace.get_current_span().get_span_context()
        if ambient.is_valid:
            return [Link(ambient)]
        return []

    @contextlib.contextmanager
    def _root_observation(
        self,
        *,
        span_name: str,
        trace_id: UUID,
        attributes: Dict[str, AttributeValue],
        observation_type: str,
        payload: Dict[str, Any],
    ) -> Iterator[ObservationHandle]:
        if not self._enabled:
            yield NULL_HANDLE
            return
        with self._span(
            span_name=span_name,
            observation_type=observation_type,
            attributes=attributes,
            parent=Context(),
            forced_trace_id=trace_id.int,
            links=self._ambient_links(),
            payload=payload,
        ) as handle:
            yield handle

    @contextlib.contextmanager
    def _span(
        self,
        *,
        span_name: str,
        observation_type: str,
        attributes: Dict[str, AttributeValue],
        parent: Context | None,
        forced_trace_id: int | None,
        links: list[Link],
        payload: Dict[str, Any],
    ) -> Iterator[ObservationHandle]:
        try:
            span = self._start_span(
                span_name=span_name,
                observation_type=observation_type,
                attributes=attributes,
                parent=parent,
                forced_trace_id=forced_trace_id,
                links=links,
            )
        except Exception as e:
            logger.warning(
                "otel_span_start_failed",
                error=str(e),
                error_type=type(e).__name__,
                observation_name=span_name,
                observation_type=observation_type,
            )
            yield NULL_HANDLE
            return
        handle = ObservationHandle(span, self._usage_recorder, initial_attributes=attributes)
        handle.update(**{key: value for key, value in payload.items() if key != "trace_context"})
        try:
            with otel_trace.use_span(
                span, end_on_exit=False, record_exception=False, set_status_on_exception=False
            ):
                yield handle
        except BaseException as exc:
            handle.record_exception(exc)
            raise
        finally:
            handle.finalize()

    def _start_span(
        self,
        *,
        span_name: str,
        observation_type: str,
        attributes: Dict[str, AttributeValue],
        parent: Context | None,
        forced_trace_id: int | None,
        links: list[Link],
    ) -> Span:
        kind = SPAN_KIND_BY_TYPE.get(observation_type, SpanKind.INTERNAL)
        if forced_trace_id is None:
            return self._tracer.start_span(
                name=span_name, context=parent, kind=kind, attributes=attributes, links=links
            )
        with force_trace_id(forced_trace_id):
            return self._tracer.start_span(
                name=span_name, context=parent, kind=kind, attributes=attributes, links=links
            )

    def _assign_root_observation_id(
        self, trace: TraceContext | ConversationTraceContext, handle: ObservationHandle
    ) -> None:
        if handle.span is None or trace.root_observation_id:
            return
        span_context = handle.span.get_span_context()
        if span_context.span_id != INVALID_SPAN_ID:
            trace.root_observation_id = format(span_context.span_id, "016x")
