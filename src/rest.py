from typing import Any
from datetime import datetime
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from infra.database import get_db

from exceptions.service_exceptions import (
    BaseServiceException,
    ServiceValidationException,
    service_http_exception_handler,
    RouterValidationException,
)
from adapters.observability.logging import get_logger, RequestLoggingMiddleware

logger = get_logger()


def init_middlewares(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)


def init_routes(app: FastAPI, controllers: list[Any]) -> None:
    @app.get("/", tags=["Root"])
    async def root() -> dict[str, Any]:
        return {
            "message": "<description>",
            "version": "1.0.0",
            "status": "running",
        }

    @app.get(
        "/health", status_code=status.HTTP_200_OK, tags=["Health"], response_model=None
    )
    async def health_check(request: Request) -> JSONResponse | dict[str, Any]:
        try:
            db_available = False
            try:
                async with get_db() as db:  # type: unused-ignore
                    await db.execute(select(1))
                    db_available = True
            except Exception:
                pass

            return {
                "status": "healthy",
                "components": {
                    "database": "ok" if db_available else "unavailable",
                    "session_model": "session-per-request",
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.exception("Health check error")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "error": str(e)},
            )

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
