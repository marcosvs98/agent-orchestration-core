# pylint: disable=import-self
import logging
from enum import Enum, StrEnum
from typing import Any
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from structlog.contextvars import bound_contextvars
import structlog
from decouple import config
from opentelemetry.trace import get_current_span
from exceptions.service_exceptions import DomainValidationException


class EnvironmentSet(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"


ENVIRONMENT: EnvironmentSet = config(
    "ENVIRONMENT",
    default=EnvironmentSet.DEVELOPMENT,
    cast=EnvironmentSet,
)


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL
    NOTSET = logging.NOTSET

    @staticmethod
    def cast_log_level(value: str) -> int:
        try:
            return LogLevel[value.upper()].value
        except KeyError as e:
            raise DomainValidationException(message=f"{value} is not a valid LogLevel") from e


LOG_LEVEL = config("LOG_LEVEL", default="INFO", cast=LogLevel.cast_log_level)


def add_trace_correlation(_logger: Any, _method_name: str, event_dict: dict) -> dict:
    span_context = get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def configure_logger(is_async: bool = False) -> None:
    structlog.stdlib.recreate_defaults()

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_trace_correlation,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.MODULE,
            }
        ),
    ]

    if is_async is True:
        wrapper_class = structlog.stdlib.AsyncBoundLogger
    else:
        wrapper_class = structlog.stdlib.BoundLogger

    logger_factory = structlog.stdlib.LoggerFactory()

    if ENVIRONMENT == EnvironmentSet.DEVELOPMENT:
        structlog.configure(
            processors=shared_processors
            + [
                structlog.dev.set_exc_info,
                structlog.dev.ConsoleRenderer(),
            ],
            context_class=dict,
            wrapper_class=wrapper_class,
            logger_factory=logger_factory,
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=shared_processors
            + [
                structlog.processors.EventRenamer("message"),
                structlog.processors.format_exc_info,
                structlog.processors.CallsiteParameterAdder(
                    {
                        structlog.processors.CallsiteParameter.PATHNAME,
                        structlog.processors.CallsiteParameter.PROCESS,
                        structlog.processors.CallsiteParameter.PROCESS_NAME,
                        structlog.processors.CallsiteParameter.THREAD,
                        structlog.processors.CallsiteParameter.THREAD_NAME,
                    }
                ),
                structlog.processors.JSONRenderer(default=str),
            ]
            + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
            context_class=dict,
            wrapper_class=wrapper_class,
            logger_factory=logger_factory,
            cache_logger_on_first_use=True,
        )


def get_logger(
    name: str | None = None, is_async: bool = False, force_configure: bool = False
) -> Any:
    if not structlog.is_configured() or force_configure:
        configure_logger(is_async=is_async)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    logger_name = name if name else __name__
    return structlog.get_logger(logger_name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        safe_headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() in {"x-request-id", "x-correlation-id", "idempotency-key", "x-trace-id"}
        }
        log_attributes: dict = {
            "request.method": request.method,
            "request.url.path": request.url.path,
            "request.headers": safe_headers,
        }
        with bound_contextvars(**log_attributes):
            response = await call_next(request)
        return response
