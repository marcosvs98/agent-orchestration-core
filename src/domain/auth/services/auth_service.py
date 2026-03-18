import time
from collections import defaultdict
from threading import Lock
from uuid import UUID

from jose import jwt

from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.tenants.repositories.tenants_repository import TenantsRepository
from domain.auth.schemas.auth import TenantTokenResponse
from fastapi import status

from exceptions.service_exceptions import (
    AuthenticationFailedException,
    NotFoundServiceException,
    RateLimitExceededException,
)
from settings import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_SECRET,
    JWT_TENANT_TOKEN_EXPIRES_SECONDS,
)
from utils.auth import AuthContext

_TENANT_TOKEN_RATE_WINDOW_SECONDS = 300
_TENANT_TOKEN_RATE_MAX_REQUESTS = 20
_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = Lock()


class AuthService:
    """Issues tenant-scoped JWTs and records audit events."""

    def __init__(
        self,
        tenants_repository: TenantsRepository,
        authoring_event_repository: AuthoringEventRepository,
    ) -> None:
        self.tenants_repository = tenants_repository
        self.authoring_event_repository = authoring_event_repository

    def _check_rate_limit(self, principal_id: str) -> None:
        now = time.time()
        cutoff = now - _TENANT_TOKEN_RATE_WINDOW_SECONDS
        with _rate_lock:
            _rate_store[principal_id] = [
                t for t in _rate_store[principal_id] if t > cutoff
            ]
            if len(_rate_store[principal_id]) >= _TENANT_TOKEN_RATE_MAX_REQUESTS:
                raise RateLimitExceededException(message="tenant_token_rate_limit")
            _rate_store[principal_id].append(now)

    async def issue_tenant_token(
        self,
        tenant_id: UUID,
        auth: AuthContext,
    ) -> TenantTokenResponse:
        """Issue a JWT for the given tenant. Caller must have tenants:create scope."""
        self._check_rate_limit(auth.principal_id)

        tenant = await self.tenants_repository.get_tenant(tenant_id)
        if tenant is None:
            raise NotFoundServiceException(message="tenant_not_found")

        now = int(time.time())
        exp = now + JWT_TENANT_TOKEN_EXPIRES_SECONDS
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "exp": exp,
            "tenant_id": str(tenant_id),
            "principal_id": auth.principal_id,
            "principal_type": auth.principal_type,
            "scopes": list(auth.scopes),
            "sub": auth.principal_id,
        }

        if not JWT_SECRET or not JWT_ISSUER or not JWT_AUDIENCE:
            raise AuthenticationFailedException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                message="auth_not_configured",
            )

        access_token = jwt.encode(
            payload,
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        if hasattr(access_token, "decode"):
            access_token = access_token.decode("utf-8")

        await self.authoring_event_repository.append_event(
            tenant_id=tenant_id,
            resource_type="tenant",
            resource_id=tenant_id,
            version_id=None,
            event_type="TENANT_TOKEN_ISSUED",
            change_type="CREATE",
            principal_id=auth.principal_id,
            justification="tenant token issued",
            schema_version=1,
        )

        return TenantTokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=JWT_TENANT_TOKEN_EXPIRES_SECONDS,
        )
