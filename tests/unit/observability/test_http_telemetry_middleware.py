from collections.abc import Iterator

from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode

from adapters.observability import http_telemetry_middleware as middleware_module
from adapters.observability.http_telemetry_middleware import (
    HttpTelemetryMiddleware,
    status_class,
)


class Harness:
    def __init__(self, client: TestClient, exporter: InMemorySpanExporter) -> None:
        self.client = client
        self.exporter = exporter

    def server_spans(self) -> list:
        return [span for span in self.exporter.get_finished_spans() if span.kind is SpanKind.SERVER]

    def only_server_span(self):
        spans = self.server_spans()
        assert len(spans) == 1, [span.name for span in spans]
        return spans[0]


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        middleware_module.otel_trace, "get_tracer", lambda *_a, **_k: provider.get_tracer("test")
    )
    monkeypatch.setattr(middleware_module, "TRACING_ENABLED", True)

    app = FastAPI()
    app.add_middleware(HttpTelemetryMiddleware)

    @app.get("/items/{item_id}")
    async def read_item(item_id: str, request: Request) -> dict:
        return {"item_id": item_id, "trace_id": request.state.trace_id}

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("exploded")

    @app.get("/teapot")
    async def teapot() -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "down"})

    with TestClient(app, raise_server_exceptions=False) as client:
        yield Harness(client, exporter)
    provider.shutdown()


@pytest.mark.parametrize(
    ("code", "expected"), [(200, "2xx"), (301, "3xx"), (404, "4xx"), (500, "5xx")]
)
def test_status_class_buckets_by_hundred(code: int, expected: str) -> None:
    assert status_class(code) == expected


def test_route_is_recorded_as_a_template_not_the_raw_path(harness: Harness) -> None:
    harness.client.get("/items/42")

    span = harness.only_server_span()
    assert span.attributes["http.route"] == "/items/{item_id}"
    assert span.name == "GET /items/{item_id}"


def test_server_span_carries_the_http_semantic_attributes(harness: Harness) -> None:
    harness.client.get("/items/7")

    span = harness.only_server_span()
    assert span.attributes["http.request.method"] == "GET"
    assert span.attributes["http.response.status_code"] == 200
    assert isinstance(span.attributes["http.response.status_code"], int)
    assert span.attributes["aoc.http.status_class"] == "2xx"
    assert span.attributes["aoc.observation.type"] == "http"
    assert span.status.status_code is StatusCode.OK


def test_server_error_responses_mark_the_span_as_failed(harness: Harness) -> None:
    harness.client.get("/teapot")

    span = harness.only_server_span()
    assert span.attributes["http.response.status_code"] == 503
    assert span.attributes["aoc.http.status_class"] == "5xx"
    assert span.status.status_code is StatusCode.ERROR


def test_a_raising_endpoint_records_the_exception_and_a_500(harness: Harness) -> None:
    harness.client.get("/boom")

    span = harness.only_server_span()
    assert span.status.status_code is StatusCode.ERROR
    assert span.attributes["http.response.status_code"] == 500
    assert [event.name for event in span.events] == ["exception"]


def test_correlation_headers_are_echoed_on_the_response(harness: Harness) -> None:
    response = harness.client.get("/items/1")

    assert response.headers["x-request-id"]
    assert response.headers["x-correlation-id"] == response.headers["x-request-id"]


def test_an_inbound_request_id_is_reused_rather_than_regenerated(harness: Harness) -> None:
    response = harness.client.get("/items/1", headers={"x-request-id": "req-abc"})

    assert response.headers["x-request-id"] == "req-abc"
    assert harness.only_server_span().attributes["request_id"] == "req-abc"


def test_an_inbound_correlation_id_is_kept_distinct_from_the_request_id(harness: Harness) -> None:
    response = harness.client.get(
        "/items/1", headers={"x-request-id": "req-1", "x-correlation-id": "corr-9"}
    )

    assert response.headers["x-correlation-id"] == "corr-9"
    assert harness.only_server_span().attributes["correlation_id"] == "corr-9"


def test_request_state_trace_id_matches_the_span(harness: Harness) -> None:
    response = harness.client.get("/items/5")

    span = harness.only_server_span()
    assert UUID(response.json()["trace_id"]).hex == format(span.context.trace_id, "032x")


def test_request_state_trace_id_is_a_uuid_the_controllers_can_call_hex_on(
    harness: Harness,
) -> None:
    response = harness.client.get("/items/5")

    assert len(UUID(response.json()["trace_id"]).hex) == 32


def test_an_inbound_trace_id_header_wins_over_the_generated_one(harness: Harness) -> None:
    supplied = "4bf92f35-77b3-4da6-a3ce-929d0e0e4736"

    response = harness.client.get("/items/5", headers={"x-trace-id": supplied})

    assert response.json()["trace_id"] == supplied


def test_an_unparseable_inbound_trace_id_falls_back_to_the_span(harness: Harness) -> None:
    response = harness.client.get("/items/5", headers={"x-trace-id": "not-a-uuid"})

    span = harness.only_server_span()
    assert UUID(response.json()["trace_id"]).hex == format(span.context.trace_id, "032x")


def test_an_inbound_traceparent_makes_the_span_a_remote_child(harness: Harness) -> None:
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    harness.client.get(
        "/items/1",
        headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"},
    )

    span = harness.only_server_span()
    assert format(span.context.trace_id, "032x") == trace_id
    assert format(span.parent.span_id, "016x") == "00f067aa0ba902b7"


def test_an_unmatched_path_does_not_leak_into_the_route_label(harness: Harness) -> None:
    harness.client.get("/no/such/path/12345")

    span = harness.only_server_span()
    assert span.attributes["http.route"] == "unmatched"


def test_requests_still_succeed_when_tracing_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(
        middleware_module.otel_trace, "get_tracer", lambda *_a, **_k: provider.get_tracer("test")
    )
    monkeypatch.setattr(middleware_module, "TRACING_ENABLED", False)

    app = FastAPI()
    app.add_middleware(HttpTelemetryMiddleware)

    @app.get("/ping")
    async def ping() -> dict:
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert exporter.get_finished_spans() == ()
    provider.shutdown()


def test_resolve_route_template_prefers_a_full_match_over_a_partial_one(
    harness: Harness,
) -> None:
    harness.client.post("/items/9")

    span = harness.only_server_span()
    assert span.attributes["http.route"] == "/items/{item_id}"
    assert span.attributes["http.response.status_code"] == 405
