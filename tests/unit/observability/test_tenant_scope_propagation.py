from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from adapters.observability import otel_bootstrap as bootstrap
from adapters.observability import otel_runtime_tracer as tracer_module
from adapters.observability.otel_runtime_tracer import OtelRuntimeTracer, _scope_attributes

TENANT = "00000000-0000-0000-0000-000000000100"


@pytest.fixture
def recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[InMemorySpanExporter, OtelRuntimeTracer]]:
    memory = InMemorySpanExporter()
    provider = TracerProvider(id_generator=bootstrap.ForcedTraceIdGenerator())
    provider.add_span_processor(bootstrap.BoundAttributeSpanProcessor())
    provider.add_span_processor(SimpleSpanProcessor(memory))
    monkeypatch.setattr(tracer_module, "TRACING_ENABLED", True)
    tracer = OtelRuntimeTracer(environment="test", runtime_version="9.9.9")
    monkeypatch.setattr(tracer, "_tracer", provider.get_tracer("test"))
    yield memory, tracer
    provider.shutdown()


def _by_name(memory: InMemorySpanExporter) -> dict[str, object]:
    return {span.name: span for span in memory.get_finished_spans()}


def test_scope_attributes_selects_only_the_scoping_keys() -> None:
    picked = _scope_attributes(
        {"tenant_id": TENANT, "agent_run_id": "a1", "flow_run_id": "f1", "noise": "x"}
    )

    assert picked == {"tenant_id": TENANT, "agent_run_id": "a1", "flow_run_id": "f1"}


def test_scope_attributes_is_empty_when_nothing_identifies_the_run() -> None:
    assert _scope_attributes({"noise": "x"}) == {}


def test_tenant_on_a_parent_observation_reaches_descendant_spans(
    recorder: tuple[InMemorySpanExporter, OtelRuntimeTracer],
) -> None:
    memory, tracer = recorder

    with tracer.observe(
        as_type="chain",
        name="domain.execution.agent_runtime.run",
        metadata={"tenant_id": TENANT, "agent_run_id": "run-1"},
    ):
        with tracer.observe(as_type="generation", name="domain.execution.agent_runtime.turn"):
            pass

    spans = _by_name(memory)
    generation = spans["domain.execution.agent_runtime.turn"]
    assert generation.attributes["tenant_id"] == TENANT
    assert generation.attributes["agent_run_id"] == "run-1"


def test_nested_tool_spans_also_inherit_the_tenant(
    recorder: tuple[InMemorySpanExporter, OtelRuntimeTracer],
) -> None:
    memory, tracer = recorder

    with tracer.observe(as_type="chain", name="run", metadata={"tenant_id": TENANT}):
        with tracer.observe(as_type="generation", name="turn"):
            with tracer.observe(as_type="tool", name="tool.call"):
                pass

    assert _by_name(memory)["tool.call"].attributes["tenant_id"] == TENANT


def test_a_child_may_override_the_inherited_tenant(
    recorder: tuple[InMemorySpanExporter, OtelRuntimeTracer],
) -> None:
    memory, tracer = recorder
    other = "11111111-1111-1111-1111-111111111111"

    with tracer.observe(as_type="chain", name="run", metadata={"tenant_id": TENANT}):
        with tracer.observe(as_type="tool", name="delegated", metadata={"tenant_id": other}):
            pass

    assert _by_name(memory)["delegated"].attributes["tenant_id"] == other


def test_observations_without_a_tenant_bind_nothing(
    recorder: tuple[InMemorySpanExporter, OtelRuntimeTracer],
) -> None:
    memory, tracer = recorder

    with tracer.observe(as_type="chain", name="anonymous"):
        with tracer.observe(as_type="tool", name="child"):
            pass

    assert "tenant_id" not in _by_name(memory)["child"].attributes


def test_the_scope_does_not_outlive_its_observation(
    recorder: tuple[InMemorySpanExporter, OtelRuntimeTracer],
) -> None:
    memory, tracer = recorder

    with tracer.observe(as_type="chain", name="scoped", metadata={"tenant_id": TENANT}):
        pass
    with tracer.observe(as_type="tool", name="after"):
        pass

    assert "tenant_id" not in _by_name(memory)["after"].attributes
