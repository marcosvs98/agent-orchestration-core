from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.utils import is_body_allowed_for_status_code
from settings import APPLICATION_NAME


class BaseServiceException(HTTPException):
    """Base exception for service application."""

    message = "An unexpected error occurred. Please contact the support."
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    name = "INTERNAL_ERROR"
    service = APPLICATION_NAME
    input_data = {}

    def __init__(
        self,
        message: str | None = None,
        status_code: int | None = None,
        detail: Any | None = None,
        name: str | None = None,
        input_data: dict | None = {},
        service: str | None = None,
        headers: dict[str, str] | None = None,
        errors: Sequence[Any] | None = None,
    ):
        self.message = message or self.message
        self.service = service or self.service
        self.name = name or self.name
        self.status_code = status_code or self.status_code
        self.input_data = input_data or self.input_data
        self.headers = headers
        self._errors = errors or []
        super().__init__(self.status_code, self.message or self.detail, self.headers)

    def errors(self) -> Sequence[Any]:
        return self._errors or []


class RouterValidationException(BaseServiceException):
    """Validation error exception (400)."""

    status_code = status.HTTP_400_BAD_REQUEST
    name = "VALIDATION_ERROR"
    message = "One or more fields were provided incorrectly."


class NotImplementedServiceException(BaseServiceException):
    """Indicate contract-only endpoints."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    name = "NOT_IMPLEMENTED"
    message = "Not implemented."


class MethodNotAllowedPlaceholderException(BaseServiceException):
    """Placeholder endpoint not yet available (planning roadmap)."""

    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    name = "METHOD_NOT_ALLOWED"
    message = "Endpoint not available."


class NotFoundServiceException(BaseServiceException):
    """Resource not found."""

    status_code = status.HTTP_404_NOT_FOUND
    name = "NOT_FOUND"
    message = "Resource not found."


class ResourceBlockedServiceException(BaseServiceException):
    """Resource cannot be used in current state (draft/disabled/etc)."""

    status_code = status.HTTP_409_CONFLICT
    name = "RESOURCE_BLOCKED"
    message = "Resource is blocked for execution."


class DomainValidationException(BaseServiceException):
    """Domain validation failed."""

    status_code = status.HTTP_400_BAD_REQUEST
    name = "DOMAIN_VALIDATION"
    message = "Invalid domain operation."


class DomainConflictException(BaseServiceException):
    """Domain conflict (e.g., policy/version mismatch)."""

    status_code = status.HTTP_409_CONFLICT
    name = "DOMAIN_CONFLICT"
    message = "Domain conflict."


class IdempotencyInProgressException(BaseServiceException):
    """Idempotent request already in progress."""

    status_code = status.HTTP_409_CONFLICT
    name = "IDEMPOTENCY_IN_PROGRESS"
    message = "Idempotent request in progress."


class InvalidTransitionException(DomainValidationException):
    """Invalid state transition."""

    name = "INVALID_TRANSITION"
    message = "Invalid transition."


class AIOutputValidationException(DomainValidationException):
    """AI output failed schema validation."""

    name = "AI_OUTPUT_VALIDATION_FAILED"
    message = "AI output validation failed."


class RagNotAllowedException(DomainValidationException):
    """RAG used for incompatible task."""

    name = "RAG_NOT_ALLOWED"
    message = "RAG not allowed for this task."


class SchemaIncompatibleException(DomainValidationException):
    """Schema mismatch."""

    name = "SCHEMA_INCOMPATIBLE"
    message = "Schema incompatible."


class HashIncompatibleException(DomainValidationException):
    """Config hash mismatch."""

    name = "CONFIG_HASH_INCOMPATIBLE"
    message = "Config hash incompatible."


class AuthenticationFailedException(BaseServiceException):
    status_code = status.HTTP_401_UNAUTHORIZED
    name = "AUTHENTICATION_FAILED"
    message = "Authentication failed."


class AuthorizationDeniedException(BaseServiceException):
    status_code = status.HTTP_403_FORBIDDEN
    name = "AUTHORIZATION_DENIED"
    message = "Authorization denied."


class RateLimitExceededException(BaseServiceException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    name = "RATE_LIMIT_EXCEEDED"
    message = "Rate limit exceeded."


class LimitExceededException(BaseServiceException):
    status_code = status.HTTP_409_CONFLICT
    name = "LIMIT_EXCEEDED"
    message = "Execution limit exceeded."


async def router_http_exception_handler(request: Request, exc: BaseServiceException) -> Response:
    """Handle BaseServiceException and format structured JSON response."""
    headers = exc.headers
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)

    correlation_id = request.headers.get("X-Correlation-Id") or request.headers.get(
        "Correlation-Id"
    )
    response_data = {
        "code": exc.name,
        "message": exc.message,
        "correlation_id": correlation_id,
        "details": {
            "service": exc.service,
            "resource": request.url.path,
            "errors": jsonable_encoder(exc.errors()),
        },
        "input_data": exc.input_data,
    }

    return JSONResponse(response_data, status_code=exc.status_code, headers=headers)


async def format_exception(reason: str, correlation_id: str, exc: BaseException) -> dict:
    if isinstance(exc, BaseServiceException):
        return {
            "correlation_id": correlation_id,
            "reason": reason,
            "code": exc.name,
            "message": exc.message,
            "errors": exc.errors(),
            "input_data": exc.input_data,
        }
    return {
        "correlation_id": correlation_id,
        "reason": reason,
        "code": type(exc).__name__,
        "message": str(exc),
        "errors": [],
        "input_data": {},
    }


ServiceValidationException = RouterValidationException
service_http_exception_handler = router_http_exception_handler
