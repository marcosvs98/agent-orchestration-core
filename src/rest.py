from typing import Any
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from infra.database import get_db

from exceptions.service_exceptions import (
    BaseServiceException,
    service_http_exception_handler,
    RouterValidationException,
)
from adapters.observability.logging import get_logger, RequestLoggingMiddleware
from settings import (
    APPLICATION_NAME,
    APPLICATION_VERSION,
    APPLICATION_DESCRIPTION,
    ENVIRONMENT,
)

logger = get_logger()

_APP_START_TIME = datetime.now(timezone.utc)


def init_middlewares(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)


def init_routes(app: FastAPI, controllers: list[Any]) -> None:
    @app.get("/", tags=["Root"])
    async def root() -> dict[str, Any]:
        """Root endpoint with service information and useful links."""
        return {
            "service": APPLICATION_NAME,
            "version": APPLICATION_VERSION,
            "description": APPLICATION_DESCRIPTION,
            "environment": ENVIRONMENT,
            "status": "running",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "links": {
                "health": "/health",
                "docs": "/docs",
                "openapi": "/openapi.json",
            },
        }

    @app.get(
        "/health",
        status_code=status.HTTP_200_OK,
        tags=["Health"],
        response_model=None,
    )
    async def health_check(request: Request) -> JSONResponse | dict[str, Any]:
        """Health check endpoint verifying all critical dependencies."""
        start_time = time.time()
        components: dict[str, Any] = {}
        overall_healthy = True

        db_start = time.time()
        db_available = False
        db_error: str | None = None
        try:
            async with get_db() as db:  # type: unused-ignore
                await db.execute(select(1))
                db_available = True
        except Exception as e:
            db_error = str(e)
            logger.warning(
                "Database health check failed",
                error=str(e),
                error_type=type(e).__name__,
            )
        db_duration = (time.time() - db_start) * 1000

        components["database"] = {
            "status": "ok" if db_available else "unavailable",
            "response_time_ms": round(db_duration, 2),
        }
        if db_error:
            components["database"]["error"] = db_error
        if not db_available:
            overall_healthy = False

        redis_start = time.time()
        redis_available = False
        redis_error: str | None = None
        try:
            container = getattr(request.app.state, "container", None)
            if container:
                redis_adapter = container.adapters.redis_adapter()
                await redis_adapter.client.ping()
                redis_available = True
        except Exception as e:
            redis_error = str(e)
            logger.warning(
                "Redis health check failed",
                error=str(e),
                error_type=type(e).__name__,
            )
        redis_duration = (time.time() - redis_start) * 1000

        components["redis"] = {
            "status": "ok" if redis_available else "unavailable",
            "response_time_ms": round(redis_duration, 2),
        }
        if redis_error:
            components["redis"]["error"] = redis_error
        if not redis_available:
            overall_healthy = False

        total_duration = (time.time() - start_time) * 1000

        response_data = {
            "status": "healthy" if overall_healthy else "degraded",
            "service": APPLICATION_NAME,
            "version": APPLICATION_VERSION,
            "environment": ENVIRONMENT,
            "components": components,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": int(
                (datetime.now(timezone.utc) - _APP_START_TIME).total_seconds()
            ),
            "response_time_ms": round(total_duration, 2),
        }

        if not overall_healthy:
            logger.warning(
                "Health check completed with degraded status",
                components=components,
                overall_healthy=overall_healthy,
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=response_data,
            )

        logger.debug(
            "Health check completed successfully",
            components=components,
            response_time_ms=round(total_duration, 2),
        )
        return response_data

    for controller in controllers:
        app.include_router(controller.router)

    @app.exception_handler(Exception)
    @app.exception_handler(BaseServiceException)
    async def service_exception_handler(
        request: Request, exc: BaseServiceException
    ) -> JSONResponse:
        if not isinstance(exc, BaseServiceException):
            exc = BaseServiceException()
        return await service_http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> None:
        validation_error = ValidationError.from_exception_data(
            "RequestValidationError", line_errors=exc.errors()
        )
        raise RouterValidationException(
            errors=validation_error.errors(include_url=False)
        )
