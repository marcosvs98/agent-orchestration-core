from uuid import UUID

from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.governance.schemas.authoring_events import (
    AuthoringEventType,
    ChangeType,
    ResourceType,
)
from domain.rag.ports.service import RagServicePort
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagConfig, RagConfigCreate, VectorStore
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class RagService(RagServicePort):
    def __init__(
        self,
        repository: RagRepository,
        authoring_events: AuthoringEventRepository,
    ) -> None:
        self.repository = repository
        self.authoring_events = authoring_events

    async def list_vector_stores(self) -> list[VectorStore]:
        stores = await self.repository.list_vector_stores()
        return [
            VectorStore(id=store.vector_store_id, name=store.name) for store in stores
        ]

    async def list_rag_configs(
        self,
        *,
        tenant_id: UUID,
        status_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[RagConfig]:
        configs = await self.repository.list_rag_configs(
            tenant_id=tenant_id, status_filter=status_filter, limit=limit
        )
        return [
            RagConfig(
                id=config.rag_config_id,
                vector_store_id=config.vector_store_id,
                options=config.options,
                status=config.status,
                version_major=config.version_major,
                version_minor=config.version_minor,
                version_patch=config.version_patch,
                config_hash=config.config_hash,
            )
            for config in configs
        ]

    async def create_rag_config(
        self,
        *,
        tenant_id: UUID,
        rag_config_create: RagConfigCreate,
        principal_id: str,
    ) -> RagConfig:
        vector_store = await self.repository.get_vector_store(
            rag_config_create.vector_store_id
        )
        if vector_store is None:
            raise NotFoundServiceException(message="vector_store_not_found")
        config_model = await self.repository.create_rag_config(
            tenant_id=tenant_id,
            source_version_id=rag_config_create.source_version_id,
            vector_store_id=rag_config_create.vector_store_id,
            options=rag_config_create.options,
            version_major=rag_config_create.version_major,
            version_minor=rag_config_create.version_minor,
            version_patch=rag_config_create.version_patch,
            config_hash=None,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CONFIG,
            resource_id=config_model.rag_config_id,
            version_id=None,
            event_type=AuthoringEventType.RAG_CONFIG_CREATED,
            change_type=ChangeType.CREATE,
            principal_id=principal_id,
            justification="create rag config",
            schema_version=1,
        )
        return RagConfig(
            id=config_model.rag_config_id,
            vector_store_id=config_model.vector_store_id,
            options=config_model.options,
            status=config_model.status,
            version_major=config_model.version_major,
            version_minor=config_model.version_minor,
            version_patch=config_model.version_patch,
            config_hash=config_model.config_hash,
        )

    async def publish_rag_config(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> RagConfig:
        config_uuid = UUID(rag_config_id)
        config = await self.repository.get_rag_config(config_uuid)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        if config.status != VersionStatus.VALIDATED:
            raise ResourceBlockedServiceException(message="rag_config_not_validated")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_rag_config_status(
            rag_config_id=config_uuid, status=VersionStatus.PUBLISHED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CONFIG,
            resource_id=config_uuid,
            version_id=None,
            event_type=AuthoringEventType.RAG_CONFIG_PUBLISHED,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_rag_config(config_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="rag_config_not_found")
        return RagConfig(
            id=refreshed.rag_config_id,
            vector_store_id=refreshed.vector_store_id,
            options=refreshed.options,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )

    async def deprecate_rag_config(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> RagConfig:
        config_uuid = UUID(rag_config_id)
        config = await self.repository.get_rag_config(config_uuid)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        if config.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="rag_config_not_published")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_rag_config_status(
            rag_config_id=config_uuid, status=VersionStatus.DEPRECATED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CONFIG,
            resource_id=config_uuid,
            version_id=None,
            event_type=AuthoringEventType.RAG_CONFIG_DEPRECATED,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_rag_config(config_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="rag_config_not_found")
        return RagConfig(
            id=refreshed.rag_config_id,
            vector_store_id=refreshed.vector_store_id,
            options=refreshed.options,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )

    async def disable_rag_config(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> RagConfig:
        config_uuid = UUID(rag_config_id)
        config = await self.repository.get_rag_config(config_uuid)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        if config.status not in (VersionStatus.PUBLISHED, VersionStatus.DEPRECATED):
            raise ResourceBlockedServiceException(
                message="rag_config_not_published_or_deprecated"
            )
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_rag_config_status(
            rag_config_id=config_uuid, status=VersionStatus.DISABLED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CONFIG,
            resource_id=config_uuid,
            version_id=None,
            event_type=AuthoringEventType.RAG_CONFIG_DISABLED,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_rag_config(config_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="rag_config_not_found")
        return RagConfig(
            id=refreshed.rag_config_id,
            vector_store_id=refreshed.vector_store_id,
            options=refreshed.options,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )
