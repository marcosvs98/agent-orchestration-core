from collections.abc import Iterator

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.propagate import get_global_textmap
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import Decision

from adapters.observability import otel_bootstrap as bootstrap


@pytest.fixture
def clean_global_state() -> Iterator[None]:
    saved = dict(bootstrap._STATE)
    try:
        yield
    finally:
        bootstrap._STATE.clear()
        bootstrap._STATE.update(saved)


@pytest.fixture
def recorder() -> Iterator[tuple[InMemorySpanExporter, otel_trace.Tracer]]:
    memory = InMemorySpanExporter()
    provider = TracerProvider(id_generator=bootstrap.ForcedTraceIdGenerator())
    provider.add_span_processor(bootstrap.BoundAttributeSpanProcessor())
    provider.add_span_processor(SimpleSpanProcessor(memory))
    yield memory, provider.get_tracer("test")
    provider.shutdown()


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("http://collector:4318", "http://collector:4318/v1/traces"),
        ("http://collector:4318/", "http://collector:4318/v1/traces"),
        ("http://collector:4318/v1/traces", "http://collector:4318/v1/traces"),
    ],
)
def test_signal_endpoint_appends_the_signal_path_exactly_once(base: str, expected: str) -> None:
    assert bootstrap.signal_endpoint(base, "traces") == expected


def test_signal_endpoint_distinguishes_signals() -> None:
    assert bootstrap.signal_endpoint("http://c:4318", "metrics").endswith("/v1/metrics")


def test_parse_otlp_headers_reads_w3c_pairs() -> None:
    assert bootstrap.parse_otlp_headers("a=1, b = 2 ") == {"a": "1", "b": "2"}


def test_parse_otlp_headers_skips_malformed_entries() -> None:
    assert bootstrap.parse_otlp_headers("") == {}
    assert bootstrap.parse_otlp_headers("novalue,,=orphan,ok=1") == {"ok": "1"}


@pytest.mark.parametrize(
    "name",
    [
        "domain.agents.agents_repository.create_agent",
        "domain.ai_policy.repository.get_model",
    ],
)
def test_repository_spans_are_detected_across_both_naming_shapes(name: str) -> None:
    assert bootstrap.is_repository_span(name) is True


def test_non_repository_spans_are_not_matched() -> None:
    assert bootstrap.is_repository_span("domain.llm.llm_executor.infer") is False


def test_sampler_thins_repository_spans_while_keeping_the_rest() -> None:
    sampler = bootstrap.ObservationSampler(default_ratio=1.0, repository_ratio=0.0)

    dropped = sampler.should_sample(None, 1234, "domain.x.some_repository.get")
    kept = sampler.should_sample(None, 1234, "domain.llm.llm_executor.infer")

    assert dropped.decision is Decision.DROP
    assert kept.decision is not Decision.DROP


def test_sampler_keeps_repository_spans_when_the_ratio_is_one() -> None:
    sampler = bootstrap.ObservationSampler(default_ratio=1.0, repository_ratio=1.0)

    result = sampler.should_sample(None, 4321, "domain.x.some_repository.get")

    assert result.decision is not Decision.DROP


def test_sampler_supports_a_partial_ratio() -> None:
    sampler = bootstrap.ObservationSampler(default_ratio=1.0, repository_ratio=0.5)

    assert "repository=0.5" in sampler.get_description()


def test_build_sampler_reports_a_description() -> None:
    assert bootstrap.build_sampler().get_description().startswith("AocObservationSampler")


def test_forced_trace_id_applies_only_inside_its_context() -> None:
    generator = bootstrap.ForcedTraceIdGenerator()
    chosen = 0x1234567890ABCDEF1234567890ABCDEF

    with bootstrap.force_trace_id(chosen):
        assert generator.generate_trace_id() == chosen

    assert generator.generate_trace_id() != chosen


def test_forced_trace_id_ignores_the_invalid_zero_id() -> None:
    generator = bootstrap.ForcedTraceIdGenerator()

    with bootstrap.force_trace_id(0):
        assert generator.generate_trace_id() != 0


def test_bound_span_attributes_default_to_empty() -> None:
    assert bootstrap.bound_span_attributes() == {}


def test_bound_span_attributes_merge_and_restore() -> None:
    with bootstrap.bind_span_attributes({"tenant_id": "t1"}):
        assert bootstrap.bound_span_attributes() == {"tenant_id": "t1"}
        with bootstrap.bind_span_attributes({"flow_id": "f1"}):
            assert bootstrap.bound_span_attributes() == {"tenant_id": "t1", "flow_id": "f1"}
        assert bootstrap.bound_span_attributes() == {"tenant_id": "t1"}

    assert bootstrap.bound_span_attributes() == {}


def test_binding_an_empty_mapping_is_a_no_op() -> None:
    with bootstrap.bind_span_attributes({}):
        assert bootstrap.bound_span_attributes() == {}


def test_bound_attributes_are_copied_onto_child_spans(
    recorder: tuple[InMemorySpanExporter, otel_trace.Tracer],
) -> None:
    memory, tracer = recorder

    with bootstrap.bind_span_attributes({"tenant_id": "t1"}):
        span = tracer.start_span("child")
        span.end()

    assert memory.get_finished_spans()[0].attributes["tenant_id"] == "t1"


def test_bound_attributes_never_overwrite_an_attribute_the_span_already_set(
    recorder: tuple[InMemorySpanExporter, otel_trace.Tracer],
) -> None:
    memory, tracer = recorder

    with bootstrap.bind_span_attributes({"aoc.observation.type": "flow", "tenant_id": "t1"}):
        span = tracer.start_span("child", attributes={"aoc.observation.type": "generation"})
        span.end()

    recorded = memory.get_finished_spans()[0]
    assert recorded.attributes["aoc.observation.type"] == "generation"
    assert recorded.attributes["tenant_id"] == "t1"


def test_build_resource_carries_service_identity() -> None:
    resource = bootstrap.build_resource(component="api", instance_id="host-1")

    assert resource.attributes["aoc.component"] == "api"
    assert resource.attributes["service.instance.id"] == "host-1"
    assert resource.attributes["service.name"]
    assert resource.attributes["deployment.environment.name"]


def test_default_instance_id_is_unique_per_call() -> None:
    assert bootstrap.default_instance_id() != bootstrap.default_instance_id()


def test_bootstrap_pins_the_propagator_and_never_enables_baggage(
    monkeypatch: pytest.MonkeyPatch, clean_global_state: None
) -> None:
    monkeypatch.setattr(bootstrap, "TRACING_ENABLED", False)
    monkeypatch.setattr(bootstrap, "METRICS_ENABLED", False)
    monkeypatch.setattr(bootstrap, "LOGS_ENABLED", False)
    bootstrap._STATE.clear()

    bootstrap.bootstrap_telemetry(component="test")

    assert "baggage" not in set(get_global_textmap().fields)
    assert "traceparent" in set(get_global_textmap().fields)


def test_bootstrap_is_idempotent(monkeypatch: pytest.MonkeyPatch, clean_global_state: None) -> None:
    monkeypatch.setattr(bootstrap, "TRACING_ENABLED", False)
    monkeypatch.setattr(bootstrap, "METRICS_ENABLED", False)
    monkeypatch.setattr(bootstrap, "LOGS_ENABLED", False)
    bootstrap._STATE.clear()

    bootstrap.bootstrap_telemetry(component="test")
    bootstrap.bootstrap_telemetry(component="second-call")

    assert bootstrap._STATE == {"bootstrapped": True}


def test_bootstrap_builds_both_providers_without_touching_the_globals(
    monkeypatch: pytest.MonkeyPatch, clean_global_state: None
) -> None:
    installed: dict[str, object] = {}
    monkeypatch.setattr(bootstrap, "TRACING_ENABLED", True)
    monkeypatch.setattr(bootstrap, "METRICS_ENABLED", True)
    monkeypatch.setattr(bootstrap, "LOGS_ENABLED", False)
    monkeypatch.setattr(bootstrap, "OTEL_EXPORTER_OTLP_HEADERS", "x-key=abc")
    monkeypatch.setattr(bootstrap, "OTLPSpanExporter", lambda **kwargs: kwargs)
    monkeypatch.setattr(bootstrap, "OTLPMetricExporter", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        bootstrap,
        "BatchSpanProcessor",
        lambda _exporter: SimpleSpanProcessor(InMemorySpanExporter()),
    )
    monkeypatch.setattr(
        bootstrap, "PeriodicExportingMetricReader", lambda _exporter, **_kwargs: None
    )
    monkeypatch.setattr(bootstrap, "MeterProvider", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        bootstrap.trace, "set_tracer_provider", lambda provider: installed.update(tracer=provider)
    )
    monkeypatch.setattr(
        bootstrap.metrics, "set_meter_provider", lambda provider: installed.update(meter=provider)
    )
    bootstrap._STATE.clear()

    bootstrap.bootstrap_telemetry(component="api", instance_id="host-1")

    assert isinstance(bootstrap._STATE["tracer_provider"], TracerProvider)
    assert installed["tracer"] is bootstrap._STATE["tracer_provider"]
    assert "meter" in installed


def test_flush_and_shutdown_are_safe_when_nothing_was_bootstrapped(
    clean_global_state: None,
) -> None:
    bootstrap._STATE.clear()

    bootstrap.flush_telemetry(10)
    bootstrap.shutdown_telemetry()


def test_flush_and_shutdown_drive_the_registered_providers(clean_global_state: None) -> None:
    provider = TracerProvider()
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    bootstrap._STATE.clear()
    bootstrap._STATE["tracer_provider"] = provider

    bootstrap.flush_telemetry(100)
    bootstrap.shutdown_telemetry()

    assert "tracer_provider" not in bootstrap._STATE
