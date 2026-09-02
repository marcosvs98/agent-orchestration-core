import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from adapters.observability import otel_bootstrap as bootstrap
from adapters.observability import otel_runtime_tracer as tracer_module
from adapters.observability.otel_runtime_tracer import OtelRuntimeTracer, deterministic_trace_id


class Recorder:
    def __init__(self, exporter: InMemorySpanExporter, tracer: OtelRuntimeTracer) -> None:
        self.exporter = exporter
        self.tracer = tracer

    def spans(self) -> tuple:
        return self.exporter.get_finished_spans()

    def named(self, name: str):
        matches = [span for span in self.spans() if span.name == name]
        assert matches, f"no span named {name} in {[s.name for s in self.spans()]}"
        return matches[0]


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Iterator[Recorder]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(
        sampler=bootstrap.build_sampler(), id_generator=bootstrap.ForcedTraceIdGenerator()
    )
    provider.add_span_processor(bootstrap.BoundAttributeSpanProcessor())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracer_module, "TRACING_ENABLED", True)
    tracer = OtelRuntimeTracer(environment="test", runtime_version="9.9.9")
    monkeypatch.setattr(tracer, "_tracer", provider.get_tracer("test"))
    yield Recorder(exporter, tracer)
    provider.shutdown()


def _flow_context(tracer: OtelRuntimeTracer, **overrides):
    payload = {
        "flow_run_id": uuid4(),
        "flow_id": uuid4(),
        "flow_version_id": uuid4(),
        "tenant_id": uuid4(),
        "session_id": uuid4(),
        "user_id": "user-7",
        "trace_id": uuid4(),
        "flow_name": "support",
    }
    payload.update(overrides)
    return tracer.start_flow_trace(**payload)


def test_explicit_trace_id_is_preserved(recorder: Recorder) -> None:
    chosen = uuid4()

    context = _flow_context(recorder.tracer, trace_id=chosen)

    assert context.trace_id == chosen


def test_trace_id_from_external_request_id_is_deterministic(recorder: Recorder) -> None:
    first = _flow_context(recorder.tracer, trace_id=None, external_request_id="req-1")
    second = _flow_context(recorder.tracer, trace_id=None, external_request_id="req-1")

    assert first.trace_id == second.trace_id
    assert first.trace_id == UUID(deterministic_trace_id("req-1"))


def test_flow_trace_falls_back_to_the_flow_run_id(recorder: Recorder) -> None:
    flow_run_id = uuid4()

    context = _flow_context(recorder.tracer, trace_id=None, flow_run_id=flow_run_id)

    assert context.trace_id == flow_run_id


def test_flow_trace_context_round_trips_every_field(recorder: Recorder) -> None:
    interaction_id, correlation_id, snapshot_id = uuid4(), uuid4(), uuid4()

    context = _flow_context(
        recorder.tracer,
        interaction_id=interaction_id,
        correlation_id=correlation_id,
        graph_snapshot_id=snapshot_id,
        execution_plan_hash="abc123",
        channel="http",
        external_message_id="m-1",
    )

    assert context.interaction_id == interaction_id
    assert context.correlation_id == correlation_id
    assert context.graph_snapshot_id == snapshot_id
    assert context.execution_plan_hash == "abc123"
    assert context.channel == "http"
    assert context.external_message_id == "m-1"
    assert context.root_observation_id is None


def test_conversation_trace_generates_an_id_when_none_is_supplied(recorder: Recorder) -> None:
    context = recorder.tracer.start_conversation_trace(
        tenant_id=uuid4(), session_id=uuid4(), user_id="u", agent_id=uuid4(), channel="http"
    )

    assert context.trace_id is not None


def test_conversation_trace_uses_a_deterministic_seed(recorder: Recorder) -> None:
    context = recorder.tracer.start_conversation_trace(
        tenant_id=uuid4(), session_id=None, user_id=None, external_request_id="req-9"
    )

    assert context.trace_id == UUID(deterministic_trace_id("req-9"))


def test_flow_span_is_a_genuine_root_carrying_the_persisted_trace_id(recorder: Recorder) -> None:
    context = _flow_context(recorder.tracer)

    with recorder.tracer.flow(trace=context, input={"a": 1}):
        pass

    span = recorder.named("flow:support")
    assert span.parent is None
    assert format(span.context.trace_id, "032x") == context.trace_id.hex


def test_flow_span_records_its_span_id_as_the_root_observation_id(recorder: Recorder) -> None:
    context = _flow_context(recorder.tracer)

    with recorder.tracer.flow(trace=context):
        assert context.root_observation_id is not None

    span = recorder.named("flow:support")
    assert context.root_observation_id == format(span.context.span_id, "016x")


def test_flow_span_stays_a_root_and_links_to_an_ambient_span(recorder: Recorder) -> None:
    outer = recorder.tracer
    context = _flow_context(outer)

    with outer.observe(as_type="span", name="ambient.request"):
        with outer.flow(trace=context):
            pass

    span = recorder.named("flow:support")
    assert span.parent is None
    assert len(span.links) == 1


def test_conversation_span_uses_the_default_name(recorder: Recorder) -> None:
    context = recorder.tracer.start_conversation_trace(
        tenant_id=uuid4(), session_id=uuid4(), user_id="u", trace_id=uuid4()
    )

    with recorder.tracer.conversation(trace=context):
        pass

    span = recorder.named("conversation.turn")
    assert format(span.context.trace_id, "032x") == context.trace_id.hex
    assert context.root_observation_id is not None


def test_children_share_the_trace_and_parent_to_the_flow(recorder: Recorder) -> None:
    context = _flow_context(recorder.tracer)

    with recorder.tracer.flow(trace=context):
        with recorder.tracer.observe(as_type="span", name="domain.execution.node"):
            pass

    flow_span = recorder.named("flow:support")
    child = recorder.named("domain.execution.node")
    assert child.context.trace_id == flow_span.context.trace_id
    assert child.parent.span_id == flow_span.context.span_id


def test_each_span_keeps_its_own_observation_type(recorder: Recorder) -> None:
    context = _flow_context(recorder.tracer)

    with recorder.tracer.flow(trace=context):
        with recorder.tracer.observe(as_type="tool", name="domain.tool.call"):
            pass

    assert recorder.named("flow:support").attributes["aoc.observation.type"] == "flow"
    assert recorder.named("domain.tool.call").attributes["aoc.observation.type"] == "tool"


@pytest.mark.parametrize(
    ("as_type", "expected"),
    [
        ("generation", SpanKind.CLIENT),
        ("embedding", SpanKind.CLIENT),
        ("retriever", SpanKind.CLIENT),
        ("tool", SpanKind.CLIENT),
        ("span", SpanKind.INTERNAL),
        ("guardrail", SpanKind.INTERNAL),
        ("chain", SpanKind.INTERNAL),
    ],
)
def test_span_kind_marks_outbound_work_as_client(
    recorder: Recorder, as_type: str, expected: SpanKind
) -> None:
    with recorder.tracer.observe(as_type=as_type, name=f"probe.{as_type}"):
        pass

    assert recorder.named(f"probe.{as_type}").kind is expected


@pytest.mark.parametrize(
    ("as_type", "operation"), [("generation", "chat"), ("embedding", "embeddings")]
)
def test_generation_spans_carry_the_gen_ai_operation(
    recorder: Recorder, as_type: str, operation: str
) -> None:
    with recorder.tracer.observe(as_type=as_type, name="domain.llm.infer", model="gpt-4o"):
        pass

    span = recorder.named("domain.llm.infer")
    assert span.attributes["gen_ai.operation.name"] == operation
    assert span.attributes["gen_ai.request.model"] == "gpt-4o"


def test_provider_and_model_metadata_are_aliased_without_losing_the_original_keys(
    recorder: Recorder,
) -> None:
    with recorder.tracer.observe(
        as_type="generation",
        name="domain.llm.infer",
        metadata={"provider": "OPENAI", "provider_model": "gpt-4o-mini"},
    ):
        pass

    span = recorder.named("domain.llm.infer")
    assert span.attributes["gen_ai.provider.name"] == "OPENAI"
    assert span.attributes["gen_ai.request.model"] == "gpt-4o-mini"
    assert span.attributes["provider"] == "OPENAI"


def test_a_later_model_update_becomes_the_response_model(recorder: Recorder) -> None:
    with recorder.tracer.observe(
        as_type="generation", name="domain.llm.infer", model="gpt-4o"
    ) as handle:
        handle.update(model="gpt-4o-2024-11-20")

    span = recorder.named("domain.llm.infer")
    assert span.attributes["gen_ai.request.model"] == "gpt-4o"
    assert span.attributes["gen_ai.response.model"] == "gpt-4o-2024-11-20"


def test_usage_and_cost_are_typed_numbers_not_json_strings(recorder: Recorder) -> None:
    with recorder.tracer.observe(
        as_type="generation", name="domain.llm.infer", model="gpt-4o"
    ) as handle:
        handle.success(
            output={"ok": True},
            usage_details={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            cost_details={"total_cost": 0.0012},
        )

    span = recorder.named("domain.llm.infer")
    assert span.attributes["gen_ai.usage.input_tokens"] == 10
    assert isinstance(span.attributes["gen_ai.usage.input_tokens"], int)
    assert span.attributes["gen_ai.usage.output_tokens"] == 20
    assert span.attributes["gen_ai.usage.total_tokens"] == 30
    assert span.attributes["aoc.gen_ai.cost.usd"] == pytest.approx(0.0012)
    assert isinstance(span.attributes["aoc.gen_ai.cost.usd"], float)


def test_model_parameters_are_recorded_under_gen_ai_names(recorder: Recorder) -> None:
    with recorder.tracer.observe(
        as_type="generation",
        name="domain.llm.infer",
        model="gpt-4o",
        model_parameters={"temperature": 0.2, "max_tokens": 512},
    ):
        pass

    span = recorder.named("domain.llm.infer")
    assert span.attributes["gen_ai.request.temperature"] == 0.2
    assert span.attributes["gen_ai.request.max_tokens"] == 512


def test_a_successful_span_ends_ok_rather_than_unset(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.op") as handle:
        handle.success(output={"status": "ok"})

    assert recorder.named("domain.x.op").status.status_code is StatusCode.OK


def test_an_untouched_span_still_ends_ok(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.quiet"):
        pass

    assert recorder.named("domain.x.quiet").status.status_code is StatusCode.OK


def test_error_marks_the_span_and_records_the_exception_shape(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="guardrail", name="domain.guardrail.check") as handle:
        handle.error(error_type="PolicyDenied", error_message="not allowed")

    span = recorder.named("domain.guardrail.check")
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes["exception.type"] == "PolicyDenied"
    assert span.attributes["exception.message"] == "not allowed"
    assert span.attributes["aoc.observation.level"] == "ERROR"


def test_error_accepts_an_explicit_status_message_and_output(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="tool", name="domain.tool.fail") as handle:
        handle.error(
            error_type="ToolError",
            error_message="boom",
            output={"detail": "x"},
            status_message="tool_failed",
            metadata={"tool_id": "t-1"},
            level="WARNING",
        )

    span = recorder.named("domain.tool.fail")
    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "tool_failed"
    assert span.attributes["tool_id"] == "t-1"


def test_status_message_on_a_successful_span_is_kept_as_an_attribute(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.noted") as handle:
        handle.success(output={}, status_message="all good")

    span = recorder.named("domain.x.noted")
    assert span.attributes["aoc.observation.status_message"] == "all good"
    assert span.status.status_code is StatusCode.OK


def test_business_exceptions_propagate_unchanged_and_mark_the_span(recorder: Recorder) -> None:
    class DomainFailure(Exception):
        pass

    with pytest.raises(DomainFailure, match="business rule"):
        with recorder.tracer.observe(as_type="span", name="domain.x.raises"):
            raise DomainFailure("business rule")

    span = recorder.named("domain.x.raises")
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes["exception.type"] == "DomainFailure"


def test_cancellation_is_recorded_and_re_raised(recorder: Recorder) -> None:
    with pytest.raises(asyncio.CancelledError):
        with recorder.tracer.observe(as_type="span", name="domain.x.cancelled"):
            raise asyncio.CancelledError()

    span = recorder.named("domain.x.cancelled")
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes["exception.type"] == "CancelledError"


def test_event_observations_attach_to_the_current_span_instead_of_creating_one(
    recorder: Recorder,
) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.parent"):
        with recorder.tracer.observe(
            as_type="event", name="event.NodeCompleted", metadata={"node_id": "n1"}
        ):
            pass

    parent = recorder.named("domain.x.parent")
    assert [event.name for event in parent.events] == ["event.NodeCompleted"]
    assert parent.events[0].attributes["node_id"] == "n1"
    assert all(span.name != "event.NodeCompleted" for span in recorder.spans())


def test_event_without_a_recording_span_is_a_silent_no_op(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="event", name="event.Orphan"):
        pass

    assert recorder.spans() == ()


def test_trace_context_with_a_parent_span_id_produces_a_remote_child(recorder: Recorder) -> None:
    trace_id = uuid4()
    parent_span_id = "00112233445566aa"

    with recorder.tracer.observe(
        as_type="span",
        name="flow.node.1",
        trace_context={"trace_id": trace_id.hex, "parent_span_id": parent_span_id},
    ):
        pass

    span = recorder.named("flow.node.1")
    assert format(span.context.trace_id, "032x") == trace_id.hex
    assert format(span.parent.span_id, "016x") == parent_span_id
    assert span.parent.is_remote is True


def test_trace_context_without_a_parent_produces_a_root_in_that_trace(recorder: Recorder) -> None:
    trace_id = uuid4()

    with recorder.tracer.observe(
        as_type="span",
        name="domain.execution.controller.create_flow_run",
        trace_context={"trace_id": trace_id.hex},
    ):
        pass

    span = recorder.named("domain.execution.controller.create_flow_run")
    assert span.parent is None
    assert format(span.context.trace_id, "032x") == trace_id.hex


@pytest.mark.parametrize(
    "trace_context",
    [
        {},
        {"trace_id": ""},
        {"trace_id": "not-hex"},
        {"trace_id": "0" * 32},
        {"parent_span_id": "00112233445566aa"},
    ],
)
def test_malformed_trace_context_never_raises(recorder: Recorder, trace_context: dict) -> None:
    with recorder.tracer.observe(
        as_type="span", name="domain.x.tolerant", trace_context=trace_context
    ):
        pass

    assert recorder.named("domain.x.tolerant").status.status_code is StatusCode.OK


def test_unparseable_parent_span_id_degrades_to_a_root(recorder: Recorder) -> None:
    trace_id = uuid4()

    with recorder.tracer.observe(
        as_type="span",
        name="domain.x.badparent",
        trace_context={"trace_id": trace_id.hex, "parent_span_id": "zzzz"},
    ):
        pass

    span = recorder.named("domain.x.badparent")
    assert span.parent is None
    assert format(span.context.trace_id, "032x") == trace_id.hex


def test_content_is_not_captured_by_default(recorder: Recorder) -> None:
    with recorder.tracer.observe(
        as_type="generation", name="domain.llm.infer", input={"prompt": "secret question"}
    ) as handle:
        handle.success(output={"answer": "secret answer"})

    span = recorder.named("domain.llm.infer")
    assert "gen_ai.input.messages" not in span.attributes
    assert "gen_ai.output.messages" not in span.attributes
    assert "secret" not in repr(dict(span.attributes))


def test_content_is_captured_when_explicitly_enabled(
    recorder: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracer_module, "OTEL_CAPTURE_CONTENT", True)

    with recorder.tracer.observe(
        as_type="generation", name="domain.llm.infer", input={"prompt": "hello"}
    ) as handle:
        handle.success(output={"answer": "world"})

    span = recorder.named("domain.llm.infer")
    assert "hello" in span.attributes["gen_ai.input.messages"]
    assert "world" in span.attributes["gen_ai.output.messages"]


def test_non_generation_content_uses_the_neutral_attribute_names(
    recorder: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tracer_module, "OTEL_CAPTURE_CONTENT", True)

    with recorder.tracer.observe(
        as_type="tool", name="domain.tool.call", input={"args": 1}
    ) as handle:
        handle.success(output={"result": 2})

    span = recorder.named("domain.tool.call")
    assert "aoc.observation.input" in span.attributes
    assert "aoc.observation.output" in span.attributes


def test_completion_start_time_is_accepted_but_never_recorded(recorder: Recorder) -> None:
    with recorder.tracer.observe(
        as_type="generation",
        name="domain.llm.infer",
        model="gpt-4o",
        completion_start_time="2026-08-17T01:00:00Z",
    ):
        pass

    span = recorder.named("domain.llm.infer")
    assert not any("completion_start" in key for key in span.attributes)


def test_unknown_kwargs_are_namespaced_rather_than_rejected(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.extra") as handle:
        handle.update(some_vendor_field="value")

    assert recorder.named("domain.x.extra").attributes["aoc.some_vendor_field"] == "value"


def test_version_is_recorded_under_a_stable_attribute(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.versioned") as handle:
        handle.update(version="v3")

    assert recorder.named("domain.x.versioned").attributes["aoc.observation.version"] == "v3"


def test_flow_identity_is_bound_onto_descendant_spans(recorder: Recorder) -> None:
    context = _flow_context(recorder.tracer)

    with recorder.tracer.flow(trace=context):
        with recorder.tracer.observe(as_type="span", name="domain.execution.node"):
            pass

    child = recorder.named("domain.execution.node")
    assert child.attributes["tenant_id"] == str(context.tenant_id)
    assert child.attributes["flow_run_id"] == str(context.flow_run_id)


def test_disabled_tracer_still_runs_the_body_and_emits_nothing(
    monkeypatch: pytest.MonkeyPatch, recorder: Recorder
) -> None:
    monkeypatch.setattr(tracer_module, "TRACING_ENABLED", False)
    disabled = OtelRuntimeTracer()
    monkeypatch.setattr(disabled, "_tracer", recorder.tracer._tracer)
    executed = []

    context = _flow_context(disabled)
    with disabled.flow(trace=context) as flow_handle:
        executed.append("flow")
        flow_handle.success(output={"status": "ok"})
    with disabled.conversation(
        trace=disabled.start_conversation_trace(
            tenant_id=uuid4(), session_id=None, user_id=None, trace_id=uuid4()
        )
    ):
        executed.append("conversation")
    with disabled.observe(as_type="span", name="domain.x.op") as handle:
        executed.append("observe")
        handle.success(output={})
        handle.error(error_type="E", error_message="m")
        handle.update(model="m")

    assert executed == ["flow", "conversation", "observe"]
    assert recorder.spans() == ()


def test_disabled_tracer_flush_and_shutdown_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tracer_module, "TRACING_ENABLED", False)
    disabled = OtelRuntimeTracer()

    disabled.flush()
    disabled.shutdown()


def test_flush_reports_failures_without_raising(
    recorder: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(_timeout: int) -> None:
        raise RuntimeError("collector unreachable")

    monkeypatch.setattr(tracer_module, "flush_telemetry", explode)

    recorder.tracer.flush()


def test_shutdown_reports_failures_without_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode() -> None:
        raise RuntimeError("already gone")

    monkeypatch.setattr(tracer_module, "shutdown_telemetry", explode)

    OtelRuntimeTracer().shutdown()


def test_a_failing_span_start_degrades_to_a_no_op_handle(
    recorder: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenTracer:
        def start_span(self, **_kwargs):
            raise RuntimeError("provider exploded")

    monkeypatch.setattr(recorder.tracer, "_tracer", BrokenTracer())
    executed = []

    with recorder.tracer.observe(as_type="span", name="domain.x.broken") as handle:
        executed.append("body")
        handle.success(output={})

    assert executed == ["body"]
    assert recorder.spans() == ()


def test_unserialisable_metadata_does_not_break_the_span(recorder: Recorder) -> None:
    @dataclass
    class Unserialisable:
        value: object

    with recorder.tracer.observe(
        as_type="span", name="domain.x.weird", metadata={"obj": Unserialisable(object())}
    ) as handle:
        handle.success(output={"nested": {"deep": object()}})

    assert recorder.named("domain.x.weird").status.status_code is StatusCode.OK


def test_handle_update_swallows_attribute_failures(
    recorder: Recorder, monkeypatch: pytest.MonkeyPatch
) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.guarded") as handle:
        monkeypatch.setattr(
            handle, "_apply", lambda _kwargs: (_ for _ in ()).throw(RuntimeError("bad"))
        )
        handle.update(anything=1)

    assert recorder.named("domain.x.guarded").status.status_code is StatusCode.OK


def test_finalize_is_idempotent(recorder: Recorder) -> None:
    with recorder.tracer.observe(as_type="span", name="domain.x.once") as handle:
        pass
    handle.finalize()

    assert len([span for span in recorder.spans() if span.name == "domain.x.once"]) == 1


def test_concurrent_flows_keep_distinct_traces_and_do_not_share_bound_attributes(
    recorder: Recorder,
) -> None:
    async def run_flow(index: int) -> str:
        context = _flow_context(recorder.tracer, flow_name=f"flow-{index}")
        with recorder.tracer.flow(trace=context):
            await asyncio.sleep(0)
            with recorder.tracer.observe(as_type="span", name=f"child-{index}"):
                await asyncio.sleep(0)
        return context.trace_id.hex

    async def drive() -> list[str]:
        return await asyncio.gather(*(run_flow(index) for index in range(50)))

    trace_ids = asyncio.run(drive())

    assert len(set(trace_ids)) == 50
    for index in range(50):
        child = recorder.named(f"child-{index}")
        assert child.attributes["flow_name"] == f"flow-{index}"
        assert format(child.context.trace_id, "032x") == trace_ids[index]


def test_forced_trace_id_does_not_leak_to_later_unrelated_spans(recorder: Recorder) -> None:
    context = _flow_context(recorder.tracer)

    with recorder.tracer.flow(trace=context):
        pass
    with recorder.tracer.observe(as_type="span", name="domain.x.after"):
        pass

    assert format(recorder.named("domain.x.after").context.trace_id, "032x") != context.trace_id.hex
