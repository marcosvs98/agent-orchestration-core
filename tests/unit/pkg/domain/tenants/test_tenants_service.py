from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.tenants.repositories.tenants_repository import TenantsRepository
from domain.tenants.schemas.tenants import TenantCreate
from domain.tenants.services.tenants_service import TenantsService
from exceptions.service_exceptions import NotFoundServiceException


class TestTenantsService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=TenantsRepository)
        repo.get_tenant = AsyncMock(return_value=None)
        repo.get_tenant_by_external_id = AsyncMock(return_value=None)
        repo.create_tenant = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock(spec=AuthoringEventRepository)
        events.append_event = AsyncMock(return_value=uuid4())
        return events

    @pytest.fixture
    def tenants_service(self, repository, authoring_events):
        return TenantsService(repository=repository, authoring_events=authoring_events)

    @pytest.mark.asyncio
    async def test_create_creates_tenant_with_success(
        self, tenants_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        external_id = uuid4()
        settings = {"feature_flag": True}
        tenant_create = TenantCreate(
            name="Test Tenant",
            external_id=external_id,
            settings=settings,
        )
        principal_id = "admin-123"

        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
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
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": external_id,
                "name": "Test Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
                "settings": settings,
            },
        )
        repository.get_tenant_by_external_id = AsyncMock(return_value=None)
        repository.create_tenant = AsyncMock(return_value=mock_tenant)

        result, created = await tenants_service.create(
            tenant_create=tenant_create, principal_id=principal_id
        )

        assert created is True
        assert result.id == tenant_id
        assert result.external_id == external_id
        assert result.name == "Test Tenant"
        assert result.settings == settings
        repository.get_tenant_by_external_id.assert_called_once_with(external_id)
        repository.create_tenant.assert_called_once()
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args
        assert call_args.kwargs["tenant_id"] == tenant_id
        assert call_args.kwargs["resource_type"] == "tenant"
        assert call_args.kwargs["resource_id"] == tenant_id
        assert call_args.kwargs["version_id"] is None
        assert call_args.kwargs["event_type"] == "TENANT_CREATED"
        assert call_args.kwargs["change_type"] == "CREATE"
        assert call_args.kwargs["principal_id"] == principal_id
        assert call_args.kwargs["justification"] == "create tenant"
        assert call_args.kwargs["schema_version"] == 1

    @pytest.mark.asyncio
    async def test_create_creates_tenant_with_minimal_fields(
        self, tenants_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        tenant_create = TenantCreate(name="Minimal Tenant")
        principal_id = "admin-123"

        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=None,
            name="Minimal Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            settings=None,
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": None,
                "name": "Minimal Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
                "settings": None,
            },
        )
        repository.create_tenant = AsyncMock(return_value=mock_tenant)

        result, created = await tenants_service.create(
            tenant_create=tenant_create, principal_id=principal_id
        )

        assert created is True
        assert result.id == tenant_id
        assert result.external_id is None
        assert result.name == "Minimal Tenant"
        assert result.settings is None
        repository.create_tenant.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_existing_tenant_ensures_default_execution_limit_policy(
        self, repository, authoring_events
    ):
        external_id = uuid4()
        tenant_id = uuid4()
        tenant_create = TenantCreate(name="Test Tenant", external_id=external_id)
        existing_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=external_id,
            name="Existing Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            settings=None,
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": external_id,
                "name": "Existing Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
                "settings": None,
            },
        )
        repository.get_tenant_by_external_id = AsyncMock(return_value=existing_tenant)
        limit_repo = MagicMock(spec=ExecutionLimitPolicyRepository)
        limit_repo.ensure_default_published_policy_for_tenant = AsyncMock()
        service = TenantsService(
            repository=repository,
            authoring_events=authoring_events,
            execution_limit_policy_repository=limit_repo,
        )

        result, created = await service.create(
            tenant_create=tenant_create, principal_id="admin-123"
        )

        assert created is False
        assert result.id == tenant_id
        limit_repo.ensure_default_published_policy_for_tenant.assert_awaited_once_with(
            tenant_id
        )

    @pytest.mark.asyncio
    async def test_create_new_tenant_ensures_default_execution_limit_policy(
        self, repository, authoring_events
    ):
        tenant_id = uuid4()
        tenant_create = TenantCreate(name="New Tenant")
        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=None,
            name="New Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            settings=None,
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": None,
                "name": "New Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
                "settings": None,
            },
        )
        repository.create_tenant = AsyncMock(return_value=mock_tenant)
        limit_repo = MagicMock(spec=ExecutionLimitPolicyRepository)
        limit_repo.ensure_default_published_policy_for_tenant = AsyncMock()
        service = TenantsService(
            repository=repository,
            authoring_events=authoring_events,
            execution_limit_policy_repository=limit_repo,
        )

        result, created = await service.create(
            tenant_create=tenant_create, principal_id="admin-123"
        )

        assert created is True
        assert result.id == tenant_id
        limit_repo.ensure_default_published_policy_for_tenant.assert_awaited_once_with(
            tenant_id
        )

    @pytest.mark.asyncio
    async def test_create_returns_existing_tenant_when_external_id_matches(
        self, tenants_service, repository, authoring_events
    ):
        external_id = uuid4()
        tenant_id = uuid4()
        tenant_create = TenantCreate(name="Test Tenant", external_id=external_id)
        principal_id = "admin-123"

        existing_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=external_id,
            name="Existing Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            settings=None,
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": external_id,
                "name": "Existing Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
                "settings": None,
            },
        )
        repository.get_tenant_by_external_id = AsyncMock(return_value=existing_tenant)

        result, created = await tenants_service.create(
            tenant_create=tenant_create, principal_id=principal_id
        )

        assert created is False
        assert result.id == tenant_id
        assert result.external_id == external_id
        assert result.name == "Existing Tenant"
        repository.get_tenant_by_external_id.assert_called_once_with(external_id)
        repository.create_tenant.assert_not_called()
        authoring_events.append_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_allows_duplicate_external_id_when_none(
        self, tenants_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        tenant_create = TenantCreate(name="Test Tenant", external_id=None)
        principal_id = "admin-123"

        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
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
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": None,
                "name": "Test Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
                "settings": None,
            },
        )
        repository.create_tenant = AsyncMock(return_value=mock_tenant)

        result, created = await tenants_service.create(
            tenant_create=tenant_create, principal_id=principal_id
        )

        assert created is True
        assert result.id == tenant_id
        repository.get_tenant_by_external_id.assert_not_called()
        repository.create_tenant.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_current_returns_tenant_when_found(
        self, tenants_service, repository
    ):
        tenant_id = uuid4()
        external_id = uuid4()
        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=external_id,
            name="Test Tenant",
            description="Test Description",
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name="John Doe",
            contact_phone="+5511999999999",
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": external_id,
                "name": "Test Tenant",
                "description": "Test Description",
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": "John Doe",
                "contact_phone": "+5511999999999",
            },
        )
        repository.get_tenant = AsyncMock(return_value=mock_tenant)

        result = await tenants_service.get_current(tenant_id=tenant_id)

        assert result.id == tenant_id
        assert result.external_id == external_id
        assert result.name == "Test Tenant"
        assert result.description == "Test Description"
        assert result.timezone == "America/Sao_Paulo"
        assert result.is_active is True
        assert result.currency == "BRL"
        assert result.language == "pt_BR"
        assert result.contact_name == "John Doe"
        assert result.contact_phone == "+5511999999999"
        repository.get_tenant.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_get_current_returns_tenant_without_external_id(
        self, tenants_service, repository
    ):
        tenant_id = uuid4()
        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id,
            external_id=None,
            name="Test Tenant",
            description=None,
            timezone="America/Sao_Paulo",
            is_active=True,
            currency="BRL",
            language="pt_BR",
            contact_name=None,
            contact_phone=None,
            to_dict=lambda: {
                "tenant_id": tenant_id,
                "external_id": None,
                "name": "Test Tenant",
                "description": None,
                "timezone": "America/Sao_Paulo",
                "is_active": True,
                "currency": "BRL",
                "language": "pt_BR",
                "contact_name": None,
                "contact_phone": None,
            },
        )
        repository.get_tenant = AsyncMock(return_value=mock_tenant)

        result = await tenants_service.get_current(tenant_id=tenant_id)

        assert result.id == tenant_id
        assert result.external_id is None
        assert result.name == "Test Tenant"
        assert result.description is None
        assert result.timezone == "America/Sao_Paulo"
        assert result.is_active is True
        assert result.currency == "BRL"
        assert result.language == "pt_BR"
        assert result.contact_name is None
        assert result.contact_phone is None

    @pytest.mark.asyncio
    async def test_get_current_raises_when_tenant_not_found(
        self, tenants_service, repository
    ):
        tenant_id = uuid4()
        repository.get_tenant = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="tenant_not_found"):
            await tenants_service.get_current(tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_get_settings_returns_settings_when_found(
        self, tenants_service, repository
    ):
        tenant_id = uuid4()
        settings = {"feature_flag": True, "max_requests": 1000}
        mock_tenant = SimpleNamespace(
            tenant_id=tenant_id, settings=settings
        )
        repository.get_tenant = AsyncMock(return_value=mock_tenant)

        result = await tenants_service.get_settings(tenant_id=tenant_id)

        assert result.id == tenant_id
        assert result.settings == settings
        repository.get_tenant.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_get_settings_returns_none_when_settings_not_set(
        self, tenants_service, repository
    ):
        tenant_id = uuid4()
        mock_tenant = SimpleNamespace(tenant_id=tenant_id, settings=None)
        repository.get_tenant = AsyncMock(return_value=mock_tenant)

        result = await tenants_service.get_settings(tenant_id=tenant_id)

        assert result.id == tenant_id
        assert result.settings is None

    @pytest.mark.asyncio
    async def test_get_settings_raises_when_tenant_not_found(
        self, tenants_service, repository
    ):
        tenant_id = uuid4()
        repository.get_tenant = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="tenant_not_found"):
            await tenants_service.get_settings(tenant_id=tenant_id)
