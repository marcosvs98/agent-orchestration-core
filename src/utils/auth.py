import time
from uuid import UUID

from fastapi import Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from settings import (
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_LEEWAY_SECONDS,
    JWT_SECRET,
)
from exceptions.service_exceptions import (
    AuthenticationFailedException,
    AuthorizationDeniedException,
)

security = HTTPBearer(auto_error=False)


class AuthContext:
    def __init__(
        self,
        *,
        tenant_id: UUID | None,
        principal_type: str,
        principal_id: str,
        scopes: set[str],
        token_issuer: str,
        token_audience: str,
        expires_at: int,
    ) -> None:
        self.tenant_id = tenant_id
        self.principal_type = principal_type
        self.principal_id = principal_id
        self.scopes = scopes
        self.token_issuer = token_issuer
        self.token_audience = token_audience
        self.expires_at = expires_at


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> AuthContext:
    if credentials is None or not credentials.scheme.lower() == "bearer":
        raise AuthenticationFailedException(message="missing_bearer_token")
    if not JWT_SECRET:
        raise AuthenticationFailedException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="auth_not_configured",
        )
    if not JWT_ISSUER or not JWT_AUDIENCE:
        raise AuthenticationFailedException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="jwt_issuer_audience_not_configured",
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False, "verify_iss": False},
        )
    except JWTError:
        raise AuthenticationFailedException(message="invalid_token") from None

    issuer = payload.get("iss")
    if issuer is None or str(issuer) != JWT_ISSUER:
        raise AuthenticationFailedException(message="invalid_token_issuer")

    audience_value = payload.get("aud")
    audience = str(audience_value) if audience_value is not None else ""
    if not audience or audience != JWT_AUDIENCE:
        raise AuthenticationFailedException(message="invalid_token_audience")

    exp_value = payload.get("exp")
    try:
        exp = int(exp_value)
    except (TypeError, ValueError):
        raise AuthenticationFailedException(message="token_exp_required") from None
    now = int(time.time())
    if exp + int(JWT_LEEWAY_SECONDS) <= now:
        raise AuthenticationFailedException(message="token_expired")

    scopes_value = payload.get("scopes")
    if scopes_value is None:
        raise AuthorizationDeniedException(message="scopes_claim_required")
    if isinstance(scopes_value, str):
        scopes = {s for s in scopes_value.split() if s}
    elif isinstance(scopes_value, list):
        scopes = {str(s) for s in scopes_value if str(s).strip()}
    else:
        raise AuthorizationDeniedException(message="scopes_claim_invalid")
    if not scopes:
        raise AuthorizationDeniedException(message="scopes_claim_empty")

    has_tenant_create_scope = "tenants:create" in scopes

    tenant_value = payload.get("tenant_id")
    if tenant_value is None:
        if not has_tenant_create_scope:
            raise AuthorizationDeniedException(message="tenant_id_claim_required")
        tenant_id = None
    else:
        try:
            tenant_id = UUID(str(tenant_value))
        except ValueError:
            raise AuthorizationDeniedException(
                message="tenant_id_claim_invalid"
            ) from None

    principal_type = payload.get("principal_type")
    if principal_type not in {"human", "machine"}:
        raise AuthorizationDeniedException(message="principal_type_claim_required")

    principal_id_value = payload.get("principal_id") or payload.get("sub")
    if principal_id_value is None or not str(principal_id_value).strip():
        raise AuthorizationDeniedException(message="principal_id_claim_required")
    principal_id = str(principal_id_value)

    return AuthContext(
        tenant_id=tenant_id,
        principal_type=str(principal_type),
        principal_id=principal_id,
        scopes=scopes,
        token_issuer=str(issuer),
        token_audience=audience,
        expires_at=exp,
    )
