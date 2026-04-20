from __future__ import annotations

from uuid import UUID

from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.governance.repositories.execution_limit_policy_repository import (
    ExecutionLimitPolicyRepository,
)
from domain.tenants.ports.service import TenantsServicePort
from domain.tenants.repositories.tenants_repository import TenantsRepository
from domain.tenants.schemas.tenants import (
    TenantCreate,
    TenantCurrentResponse,
    TenantResponse,
    TenantSettingsResponse,
)
from exceptions.service_exceptions import NotFoundServiceException


class TenantsService(TenantsServicePort):
    def __init__(
        self,
        repository: TenantsRepository,
        authoring_events: AuthoringEventRepository,
        execution_limit_policy_repository: ExecutionLimitPolicyRepository | None = None,
    ) -> None:
        self.repository = repository
        self.authoring_events = authoring_events
        self.execution_limit_policy_repository = execution_limit_policy_repository

    async def create(
        self, *, tenant_create: TenantCreate, principal_id: str
    ) -> tuple[TenantResponse, bool]:
        if tenant_create.external_id is not None:
            existing = await self.repository.get_tenant_by_external_id(tenant_create.external_id)
            if existing is not None:
                if self.execution_limit_policy_repository is not None:
                    await self.execution_limit_policy_repository.ensure_default_published_policy_for_tenant(
                        existing.tenant_id
                    )
                tenant_dict = existing.to_dict()
                tenant_dict["id"] = tenant_dict.pop("tenant_id")
                return TenantResponse.model_validate(tenant_dict), False

        model = await self.repository.create_tenant(
            tenant_data=tenant_create.model_dump(mode="json")
        )
        if self.execution_limit_policy_repository is not None:
            await self.execution_limit_policy_repository.ensure_default_published_policy_for_tenant(
                model.tenant_id
            )
        await self.authoring_events.append_event(
            tenant_id=model.tenant_id,
            resource_type="tenant",
            resource_id=model.tenant_id,
            version_id=None,
            event_type="TENANT_CREATED",
            change_type="CREATE",
            principal_id=principal_id,
            justification="create tenant",
            schema_version=1,
        )
        tenant_dict = model.to_dict()
        tenant_dict["id"] = tenant_dict.pop("tenant_id")
        return TenantResponse.model_validate(tenant_dict), True

    async def get_current(self, *, tenant_id: UUID) -> TenantCurrentResponse:
        tenant = await self.repository.get_tenant(tenant_id)
        if tenant is None:
            raise NotFoundServiceException(message="tenant_not_found")
        tenant_dict = tenant.to_dict()
        tenant_dict["id"] = tenant_dict.pop("tenant_id")
        return TenantCurrentResponse.model_validate(tenant_dict)

    async def get_settings(self, *, tenant_id: UUID) -> TenantSettingsResponse:
        tenant = await self.repository.get_tenant(tenant_id)
        if tenant is None:
            raise NotFoundServiceException(message="tenant_not_found")
        return TenantSettingsResponse(id=tenant.tenant_id, settings=tenant.settings)
