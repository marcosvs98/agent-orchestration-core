from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.tenants.controllers.tenants_controller import TenantsController
from domain.tenants.schemas.tenants import TenantCreate, TenantResponse
from domain.tenants.services.tenants_service import TenantsService
from exceptions.service_exceptions import (
    AuthorizationDeniedException,
    DomainConflictException,
)
from utils.auth import AuthContext


class TestTenantsController:
    @pytest.fixture
    def service(self):
        svc = MagicMock(spec=TenantsService)
        svc.create = AsyncMock()
        svc.get_current = AsyncMock()
        svc.get_settings = AsyncMock()
        return svc

    @pytest.fixture
    def controller(self, service):
        return TenantsController(service=service)

    @pytest.mark.asyncio
    async def test_create_returns_tenant_when_scope_present(
        self, controller, service
    ):
        tenant_id = uuid4()
        external_id = uuid4()
        settings = {"feature_flag": True}
        tenant_create = TenantCreate(
            name="Test Tenant", external_id=external_id, settings=settings
        )
        principal_id = "admin-123"

        auth = AuthContext(
            tenant_id=None,
            principal_type="human",
            principal_id=principal_id,
            scopes={"tenants:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        expected_response = TenantResponse(
            id=tenant_id,
            external_id=external_id,
            name="Test Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            settings=settings,
        )
        service.create = AsyncMock(return_value=expected_response)

        result = await controller.create(tenant_create=tenant_create, auth=auth)

        assert result.id == tenant_id
        assert result.external_id == external_id
        assert result.name == "Test Tenant"
        assert result.settings == settings
        service.create.assert_called_once_with(
            tenant_create=tenant_create, principal_id=principal_id
        )

    @pytest.mark.asyncio
    async def test_create_raises_when_scope_missing(self, controller, service):
        tenant_create = TenantCreate(name="Test Tenant")
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
            await controller.create(tenant_create=tenant_create, auth=auth)

        service.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_works_with_tenant_id_in_token(
        self, controller, service
    ):
        tenant_id = uuid4()
        tenant_create = TenantCreate(name="Test Tenant")
        principal_id = "admin-123"

        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id=principal_id,
            scopes={"tenants:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        expected_response = TenantResponse(
            id=uuid4(),
            external_id=None,
            name="Test Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            settings=None,
        )
        service.create = AsyncMock(return_value=expected_response)

        result = await controller.create(tenant_create=tenant_create, auth=auth)

        assert result is not None
        assert result.name == "Test Tenant"
        service.create.assert_called_once_with(
            tenant_create=tenant_create, principal_id=principal_id
        )

    @pytest.mark.asyncio
    async def test_create_raises_when_external_id_duplicate(
        self, controller, service
    ):
        external_id = uuid4()
        tenant_create = TenantCreate(name="Test Tenant", external_id=external_id)
        principal_id = "admin-123"

        auth = AuthContext(
            tenant_id=None,
            principal_type="human",
            principal_id=principal_id,
            scopes={"tenants:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        service.create = AsyncMock(
            side_effect=DomainConflictException(message="external_id_already_exists")
        )

        with pytest.raises(DomainConflictException, match="external_id_already_exists"):
            await controller.create(tenant_create=tenant_create, auth=auth)

        service.create.assert_called_once_with(
            tenant_create=tenant_create, principal_id=principal_id
        )

    @pytest.mark.asyncio
    async def test_create_with_all_fields(
        self, controller, service
    ):
        tenant_id = uuid4()
        external_id = uuid4()
        tenant_create = TenantCreate(
            name="Full Tenant",
            external_id=external_id,
            description="Full description",
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name="John Doe",
            contact_phone="+5511999999999",
            settings={"feature_flag": True},
        )
        principal_id = "admin-123"

        auth = AuthContext(
            tenant_id=None,
            principal_type="human",
            principal_id=principal_id,
            scopes={"tenants:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        expected_response = TenantResponse(
            id=tenant_id,
            external_id=external_id,
            name="Full Tenant",
            description="Full description",
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name="John Doe",
            contact_phone="+5511999999999",
            settings={"feature_flag": True},
        )
        service.create = AsyncMock(return_value=expected_response)

        result = await controller.create(tenant_create=tenant_create, auth=auth)

        assert result.id == tenant_id
        assert result.name == "Full Tenant"
        assert result.description == "Full description"
        assert result.contact_name == "John Doe"
        assert result.contact_phone == "+5511999999999"
        service.create.assert_called_once_with(
            tenant_create=tenant_create, principal_id=principal_id
        )
