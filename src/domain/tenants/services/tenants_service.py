from uuid import UUID

from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.tenants.ports.service import TenantsServicePort
from domain.tenants.repositories.tenants_repository import TenantsRepository
from domain.tenants.schemas.tenants import (
    TenantCreate,
    TenantCurrentResponse,
    TenantResponse,
    TenantSettingsResponse,
)
from exceptions.service_exceptions import (
    DomainConflictException,
    NotFoundServiceException,
)


class TenantsService(TenantsServicePort):
    def __init__(
        self,
        repository: TenantsRepository,
        authoring_events: AuthoringEventRepository,
    ) -> None:
        self.repository = repository
        self.authoring_events = authoring_events

    async def create(
        self, *, tenant_create: TenantCreate, principal_id: str
    ) -> TenantResponse:
        if tenant_create.external_id is not None:
            existing = await self.repository.get_tenant_by_external_id(
                tenant_create.external_id
            )
            if existing is not None:
                raise DomainConflictException(message="external_id_already_exists")

        model = await self.repository.create_tenant(
            tenant_data=tenant_create.model_dump(mode="json")
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
        return TenantResponse.model_validate(tenant_dict)

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
