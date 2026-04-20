from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.auth.controllers.auth_controller import AuthController
from domain.auth.schemas.auth import TenantTokenRequest, TenantTokenResponse
from domain.auth.services.auth_service import AuthService
from exceptions.service_exceptions import AuthorizationDeniedException
from utils.auth import AuthContext


class TestAuthController:
    @pytest.fixture
    def service(self):
        svc = MagicMock(spec=AuthService)
        svc.issue_tenant_token = AsyncMock()
        return svc

    @pytest.fixture
    def controller(self, service):
        return AuthController(service=service)

    @pytest.mark.asyncio
    async def test_issue_tenant_token_returns_token_when_scope_present(
        self, controller, service
    ):
        tenant_id = uuid4()
        body = TenantTokenRequest(tenant_id=tenant_id)
        auth = AuthContext(
            tenant_id=None,
            principal_type="human",
            principal_id="admin-123",
            scopes={"tenants:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        expected = TenantTokenResponse(
            access_token="eyJ...",
            token_type="bearer",
            expires_in=3600,
        )
        service.issue_tenant_token = AsyncMock(return_value=expected)

        result = await controller.issue_tenant_token(body=body, auth=auth)

        assert result.access_token == "eyJ..."
        assert result.token_type == "bearer"
        assert result.expires_in == 3600
        service.issue_tenant_token.assert_called_once_with(
            tenant_id=tenant_id,
            auth=auth,
        )

    @pytest.mark.asyncio
    async def test_issue_tenant_token_raises_when_scope_missing(
        self, controller, service
    ):
        body = TenantTokenRequest(tenant_id=uuid4())
        auth = AuthContext(
            tenant_id=None,
            principal_type="human",
            principal_id="admin-123",
            scopes={"flows:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        with pytest.raises(AuthorizationDeniedException, match="insufficient_scope"):
            await controller.issue_tenant_token(body=body, auth=auth)

        service.issue_tenant_token.assert_not_called()
