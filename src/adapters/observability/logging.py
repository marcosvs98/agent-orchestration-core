# pylint: disable=import-self
import logging
from enum import Enum, StrEnum
from typing import Any
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bound_contextvars
import structlog
from decouple import config
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
            raise DomainValidationException(
                message=f"{value} is not a valid LogLevel"
            ) from e


LOG_LEVEL = config(
    "LOG_LEVEL", default="DEBUG", cast=LogLevel.cast_log_level
)  # TODO: REVER aqui


def configure_logger(is_async: bool = False) -> None:
    structlog.stdlib.recreate_defaults()

    shared_processors = [
        structlog.contextvars.merge_contextvars,
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
    async def dispatch(self, request, call_next) -> Response:
        log_attributes: dict = {
            "request.method": request.method,
            "request.url": str(request.url),
            "request.url.path": request.url.path,
            "request.query_params": dict(request.query_params),
            "request.user_agent": request.headers.get("User-Agent"),
            "request.referer": request.headers.get("Referer"),
            "request.headers": dict(request.headers),
        }
        with bound_contextvars(**log_attributes):
            response = await call_next(request)
        return response
