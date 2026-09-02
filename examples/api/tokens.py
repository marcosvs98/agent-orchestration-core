from __future__ import annotations

import time
from typing import Final, List
from uuid import UUID

from jose import jwt

import settings
from domain.governance.schemas.scopes import Scope

DEFAULT_TTL_SECONDS: Final[int] = 3600


def all_scopes() -> List[str]:
    return [scope.value for scope in Scope]


def mint_admin_token(
    *,
    tenant_id: UUID | None = None,
    principal_id: str = "examples-admin",
    principal_type: str = "human",
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    if not settings.JWT_SECRET:
        raise SystemExit("JWT_SECRET is not configured; copy env.example to .env and set it")
    if not settings.JWT_ISSUER:
        raise SystemExit("JWT_ISSUER is not configured")
    if not settings.JWT_AUDIENCE:
        raise SystemExit("JWT_AUDIENCE is not configured")

    now = int(time.time())
    payload = {
        "principal_id": principal_id,
        "principal_type": principal_type,
        "scopes": all_scopes(),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "exp": now + ttl_seconds,
        "iat": now,
    }
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
