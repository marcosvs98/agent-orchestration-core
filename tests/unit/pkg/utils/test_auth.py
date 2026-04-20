from uuid import uuid4

import pytest
from jose import jwt
from fastapi.security import HTTPAuthorizationCredentials

from exceptions.service_exceptions import (
    AuthenticationFailedException,
    AuthorizationDeniedException,
)
from utils import auth as auth_module


def _make_token(*, secret: str, algorithm: str, claims: dict) -> str:
    return jwt.encode(claims, secret, algorithm=algorithm)


class TestAuth:
    def setup_method(self):
        auth_module.JWT_SECRET = "test-secret"
        auth_module.JWT_ALGORITHM = "HS256"
        auth_module.JWT_ISSUER = "test-issuer"
        auth_module.JWT_AUDIENCE = "test-audience"
        auth_module.JWT_LEEWAY_SECONDS = 0

    def test_get_auth_context_valid_token(self):
        token = _make_token(
            secret=auth_module.JWT_SECRET,
            algorithm=auth_module.JWT_ALGORITHM,
            claims={
                "iss": auth_module.JWT_ISSUER,
                "aud": auth_module.JWT_AUDIENCE,
                "exp": 9999999999,
                "tenant_id": str(uuid4()),
                "principal_type": "machine",
                "principal_id": "integration-1",
                "scopes": ["execution:flow_run:create"],
            },
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        ctx = auth_module.get_auth_context(credentials=credentials)
        assert ctx.tenant_id is not None
        assert ctx.principal_type == "machine"
        assert ctx.principal_id == "integration-1"
        assert "execution:flow_run:create" in ctx.scopes

    def test_get_auth_context_missing_exp_raises(self):
        token = _make_token(
            secret=auth_module.JWT_SECRET,
            algorithm=auth_module.JWT_ALGORITHM,
            claims={
                "iss": auth_module.JWT_ISSUER,
                "aud": auth_module.JWT_AUDIENCE,
                "tenant_id": str(uuid4()),
                "principal_type": "machine",
                "principal_id": "integration-1",
                "scopes": ["execution:flow_run:create"],
            },
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(AuthenticationFailedException):
            auth_module.get_auth_context(credentials=credentials)

    def test_get_auth_context_missing_tenant_id_raises(self):
        token = _make_token(
            secret=auth_module.JWT_SECRET,
            algorithm=auth_module.JWT_ALGORITHM,
            claims={
                "iss": auth_module.JWT_ISSUER,
                "aud": auth_module.JWT_AUDIENCE,
                "exp": 9999999999,
                "principal_type": "machine",
                "principal_id": "integration-1",
                "scopes": ["execution:flow_run:create"],
            },
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(AuthorizationDeniedException):
            auth_module.get_auth_context(credentials=credentials)

    def test_get_auth_context_allows_tenant_id_none_with_tenants_create_scope(self):
        token = _make_token(
            secret=auth_module.JWT_SECRET,
            algorithm=auth_module.JWT_ALGORITHM,
            claims={
                "iss": auth_module.JWT_ISSUER,
                "aud": auth_module.JWT_AUDIENCE,
                "exp": 9999999999,
                "principal_type": "human",
                "principal_id": "admin-123",
                "scopes": ["tenants:create"],
            },
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        ctx = auth_module.get_auth_context(credentials=credentials)
        assert ctx.tenant_id is None
        assert ctx.principal_type == "human"
        assert ctx.principal_id == "admin-123"
        assert "tenants:create" in ctx.scopes

    def test_get_auth_context_allows_tenant_id_with_tenants_create_scope(self):
        tenant_id = uuid4()
        token = _make_token(
            secret=auth_module.JWT_SECRET,
            algorithm=auth_module.JWT_ALGORITHM,
            claims={
                "iss": auth_module.JWT_ISSUER,
                "aud": auth_module.JWT_AUDIENCE,
                "exp": 9999999999,
                "tenant_id": str(tenant_id),
                "principal_type": "human",
                "principal_id": "admin-123",
                "scopes": ["tenants:create"],
            },
        )
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        ctx = auth_module.get_auth_context(credentials=credentials)
        assert ctx.tenant_id == tenant_id
        assert ctx.principal_type == "human"
        assert ctx.principal_id == "admin-123"
        assert "tenants:create" in ctx.scopes
