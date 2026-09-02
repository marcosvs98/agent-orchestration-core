import hashlib
import secrets
import time
from collections import defaultdict
from threading import Lock
from uuid import UUID

from jose import jwt

from adapters.cache.redis_adapter import RedisAdapter
from domain.auth.repositories.inbound_service_key_repository import (
    InboundServiceKeyRepository,
)
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.governance.schemas.scopes import Scope
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

NON_DELEGABLE_SCOPES: frozenset[str] = frozenset({Scope.TenantsCreate.value})


class AuthService:
    def __init__(
        self,
        tenants_repository: TenantsRepository,
        authoring_event_repository: AuthoringEventRepository,
        inbound_service_key_repository: InboundServiceKeyRepository,
        cache_adapter: RedisAdapter | None = None,
    ) -> None:
        self.tenants_repository = tenants_repository
        self.authoring_event_repository = authoring_event_repository
        self.inbound_service_key_repository = inbound_service_key_repository
        self.cache_adapter = cache_adapter

    @staticmethod
    def _check_local_rate_limit(principal_id: str) -> None:
        now = time.time()
        cutoff = now - _TENANT_TOKEN_RATE_WINDOW_SECONDS
        with _rate_lock:
            _rate_store[principal_id] = [t for t in _rate_store[principal_id] if t > cutoff]
            if len(_rate_store[principal_id]) >= _TENANT_TOKEN_RATE_MAX_REQUESTS:
                raise RateLimitExceededException(message="tenant_token_rate_limit")
            _rate_store[principal_id].append(now)

    async def _check_rate_limit(self, principal_id: str) -> None:
        if self.cache_adapter is None:
            self._check_local_rate_limit(principal_id)
            return
        used = await self.cache_adapter.incr_with_ttl(
            f"auth:tenant_token_rate:{principal_id}",
            ttl=_TENANT_TOKEN_RATE_WINDOW_SECONDS,
        )
        if not isinstance(used, int):
            self._check_local_rate_limit(principal_id)
            return
        if used > _TENANT_TOKEN_RATE_MAX_REQUESTS:
            raise RateLimitExceededException(message="tenant_token_rate_limit")

    async def issue_tenant_token(
        self,
        tenant_id: UUID,
        auth: AuthContext,
    ) -> TenantTokenResponse:
        await self._check_rate_limit(auth.principal_id)

        tenant = await self.tenants_repository.get_tenant(tenant_id)
        if tenant is None:
            raise NotFoundServiceException(message="tenant_not_found")

        now = int(time.time())
        exp = now + JWT_TENANT_TOKEN_EXPIRES_SECONDS
        delegated_scopes = sorted(auth.scopes - NON_DELEGABLE_SCOPES)
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "exp": exp,
            "tenant_id": str(tenant_id),
            "principal_id": auth.principal_id,
            "principal_type": auth.principal_type,
            "scopes": delegated_scopes,
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
        if isinstance(access_token, bytes):
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

    async def create_inbound_service_key(
        self,
        tenant_id: UUID,
        auth: AuthContext,
    ) -> tuple[UUID, UUID, str]:
        tenant = await self.tenants_repository.get_tenant(tenant_id)
        if tenant is None:
            raise NotFoundServiceException(message="tenant_not_found")
        secret = secrets.token_urlsafe(48)
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        row = await self.inbound_service_key_repository.insert_key(tenant_id, digest)
        await self.authoring_event_repository.append_event(
            tenant_id=tenant_id,
            resource_type="tenant_inbound_service_key",
            resource_id=row.inbound_service_key_id,
            version_id=None,
            event_type="TENANT_INBOUND_SERVICE_KEY_CREATED",
            change_type="CREATE",
            principal_id=auth.principal_id,
            justification="inbound service key created",
            schema_version=1,
        )
        return row.inbound_service_key_id, tenant_id, secret

    async def revoke_inbound_service_key(
        self,
        inbound_service_key_id: UUID,
        tenant_id: UUID,
        auth: AuthContext,
    ) -> None:
        ok = await self.inbound_service_key_repository.revoke_key(
            inbound_service_key_id,
            tenant_id,
        )
        if not ok:
            raise NotFoundServiceException(message="inbound_service_key_not_found")
        await self.authoring_event_repository.append_event(
            tenant_id=tenant_id,
            resource_type="tenant_inbound_service_key",
            resource_id=inbound_service_key_id,
            version_id=None,
            event_type="TENANT_INBOUND_SERVICE_KEY_REVOKED",
            change_type="UPDATE",
            principal_id=auth.principal_id,
            justification="inbound service key revoked",
            schema_version=1,
        )
