from __future__ import annotations

import time
from typing import Any, Dict, Final
from uuid import UUID, uuid4

from opentelemetry import trace as otel_trace
from opentelemetry.propagate import extract
from opentelemetry.trace import Span, Status, StatusCode, SpanKind
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

from adapters.observability.logging import get_logger
from adapters.observability.otel_attributes import (
    HTTP_REQUEST_METHOD,
    HTTP_RESPONSE_STATUS_CODE,
    HTTP_ROUTE,
    HTTP_STATUS_CLASS,
    NETWORK_PROTOCOL_VERSION,
    OBSERVATION_TYPE,
    AttributeValue,
)
from adapters.observability.otel_bootstrap import INSTRUMENTATION_SCOPE
from settings import APPLICATION_VERSION, TRACING_ENABLED

logger = get_logger()

TRACE_ID_HEADER: Final[str] = "x-trace-id"
REQUEST_ID_HEADER: Final[str] = "x-request-id"
CORRELATION_ID_HEADER: Final[str] = "x-correlation-id"
UNMATCHED_ROUTE: Final[str] = "unmatched"


def resolve_route_template(request: Request) -> str:
    best = UNMATCHED_ROUTE
    for route in request.app.routes:
        path = getattr(route, "path", None)
        if path is None:
            continue
        match, _ = route.matches(request.scope)
        if match is Match.FULL:
            return str(path)
        if match is Match.PARTIAL and best is UNMATCHED_ROUTE:
            best = str(path)
    return best


def status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


class HttpTelemetryMiddleware(BaseHTTPMiddleware):
    @staticmethod
    def _as_trace_uuid(value: str | None) -> UUID | None:
        candidate = (value or "").strip()
        if not candidate:
            return None
        try:
            return UUID(candidate)
        except ValueError:
            return None

    @staticmethod
    def _stamp_tenant(span: Span, request: Request) -> None:
        tenant_id = request.scope.get("state", {}).get("tenant_id")
        if isinstance(tenant_id, str) and tenant_id:
            span.set_attribute("tenant_id", tenant_id)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or request_id
        inbound_trace_id = request.headers.get(TRACE_ID_HEADER)

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.trace_id = self._as_trace_uuid(inbound_trace_id)

        if not TRACING_ENABLED:
            response = await call_next(request)
            self._echo_headers(response, request_id, correlation_id)
            return response

        route = resolve_route_template(request)
        attributes: Dict[str, AttributeValue] = {
            HTTP_REQUEST_METHOD: request.method,
            HTTP_ROUTE: route,
            NETWORK_PROTOCOL_VERSION: request.scope.get("http_version", ""),
            OBSERVATION_TYPE: "http",
            "request_id": request_id,
            "correlation_id": correlation_id,
        }

        tracer = otel_trace.get_tracer(INSTRUMENTATION_SCOPE, APPLICATION_VERSION)
        parent = extract(dict(request.headers))
        started = time.perf_counter()
        with tracer.start_as_current_span(
            name=f"{request.method} {route}",
            context=parent,
            kind=SpanKind.SERVER,
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            span_context = span.get_span_context()
            if span_context.is_valid:
                request.state.trace_id = self._as_trace_uuid(inbound_trace_id) or UUID(
                    int=span_context.trace_id
                )
            try:
                response = await call_next(request)
            except BaseException as exc:
                self._stamp_tenant(span, request)
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                span.set_attribute(HTTP_RESPONSE_STATUS_CODE, 500)
                span.set_attribute(HTTP_STATUS_CLASS, status_class(500))
                self._log_access(
                    method=request.method,
                    route=route,
                    status_code=500,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    error_type=type(exc).__name__,
                )
                raise
            self._stamp_tenant(span, request)
            span.set_attribute(HTTP_RESPONSE_STATUS_CODE, response.status_code)
            span.set_attribute(HTTP_STATUS_CLASS, status_class(response.status_code))
            if response.status_code >= 500:
                span.set_status(Status(StatusCode.ERROR, status_class(response.status_code)))
            else:
                span.set_status(Status(StatusCode.OK))
            self._log_access(
                method=request.method,
                route=route,
                status_code=response.status_code,
                duration_ms=(time.perf_counter() - started) * 1000,
                request_id=request_id,
                correlation_id=correlation_id,
                error_type=None,
            )
        self._echo_headers(response, request_id, correlation_id)
        return response

    def _echo_headers(self, response: Response, request_id: str, correlation_id: str) -> None:
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[CORRELATION_ID_HEADER] = correlation_id

    def _log_access(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
        request_id: str,
        correlation_id: str,
        error_type: str | None,
    ) -> None:
        logger.info(
            "http_access",
            http_method=method,
            http_route=route,
            http_status_code=status_code,
            http_status_class=status_class(status_code),
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
            correlation_id=correlation_id,
            error_type=error_type,
        )
