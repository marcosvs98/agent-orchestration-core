#!/usr/bin/env python3
"""Generate admin JWT for development.

Reads .env and emits a token with all scopes. Default tenant is demo (flow 000700).
Use ADMIN_TENANT_ID in .env to override.
"""

import sys
import time

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000100"

try:
    from decouple import config
    from jose import jwt
except ImportError as e:
    print(f"ERRO: Dependência não instalada: {e}", file=sys.stderr)
    print("Instale com: pip install python-jose[cryptography] python-decouple", file=sys.stderr)
    sys.exit(1)

try:
    from domain.governance.schemas.scopes import Scope
except ImportError:
    print("ERRO: Não foi possível importar Scope do domínio", file=sys.stderr)
    print("Certifique-se de que PYTHONPATH=src está configurado", file=sys.stderr)
    sys.exit(1)


def get_all_scopes() -> list[str]:
    """Retorna todos os scopes disponíveis no sistema."""
    return [scope.value for scope in Scope]


def generate_admin_token() -> str:
    """Gera token JWT de admin com todos os scopes."""
    secret = config("JWT_SECRET", default="")
    if not secret:
        print("ERRO: JWT_SECRET não configurado no .env", file=sys.stderr)
        sys.exit(1)

    issuer = config("JWT_ISSUER", default="")
    if not issuer:
        print("ERRO: JWT_ISSUER não configurado no .env", file=sys.stderr)
        sys.exit(1)

    audience = config("JWT_AUDIENCE", default="")
    if not audience:
        print("ERRO: JWT_AUDIENCE não configurado no .env", file=sys.stderr)
        sys.exit(1)

    algorithm = config("JWT_ALGORITHM", default="HS256")
    tenant_id = config("ADMIN_TENANT_ID", default=DEMO_TENANT_ID) or DEMO_TENANT_ID
    principal_id = config("ADMIN_PRINCIPAL_ID", default="admin-dev")
    principal_type = config("ADMIN_PRINCIPAL_TYPE", default="human")
    expires_in = config("ADMIN_TOKEN_EXPIRES_IN", default=86400 * 100, cast=int)

    now = int(time.time())
    payload = {
        "tenant_id": tenant_id,
        "principal_id": principal_id,
        "principal_type": principal_type,
        "scopes": get_all_scopes(),
        "iss": issuer,
        "aud": audience,
        "exp": now + expires_in,
        "iat": now,
    }

    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token


if __name__ == "__main__":
    try:
        token = generate_admin_token()
        tenant_id = config("ADMIN_TENANT_ID", default=DEMO_TENANT_ID) or DEMO_TENANT_ID
        hint = " (demo flow)" if tenant_id == DEMO_TENANT_ID else ""
        print(f"Token tenant_id={tenant_id}{hint}. Use ?token=... in chat URL.", file=sys.stderr)
        print(token)
    except Exception as e:
        print(f"ERRO ao gerar token: {e}", file=sys.stderr)
        sys.exit(1)
