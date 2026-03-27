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
from domain.rag.schemas.rag import (
    RagChunkingRule,
    RagChunkingRuleCreate,
    RagChunkingRuleUpdate,
    RagConfig,
    RagConfigCreate,
    RagConfigOptions,
    RagCorpusKind,
    VectorStore,
    VectorStoreCreate,
    parse_rag_chunking_rule_params,
)
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

    async def list_vector_stores(self, *, tenant_id: UUID) -> list[VectorStore]:
        stores = await self.repository.list_vector_stores(tenant_id=tenant_id)
        return [
            VectorStore(
                id=store.vector_store_id,
                name=store.name,
                embedding_model=store.embedding_model,
                embedding_dimension=store.embedding_dimension,
                metric=store.metric,
                version=store.version,
                active=store.active,
            )
            for store in stores
        ]

    async def create_vector_store(
        self, *, tenant_id: UUID, vector_store_create: VectorStoreCreate
    ) -> VectorStore:
        created = await self.repository.create_vector_store(
            tenant_id=tenant_id,
            name=vector_store_create.name,
            embedding_model=vector_store_create.embedding_model,
            embedding_dimension=vector_store_create.embedding_dimension,
            metric=vector_store_create.metric,
            version=vector_store_create.version,
            active=vector_store_create.active,
        )
        return VectorStore(
            id=created.vector_store_id,
            name=created.name,
            embedding_model=created.embedding_model,
            embedding_dimension=created.embedding_dimension,
            metric=created.metric,
            version=created.version,
            active=created.active,
        )

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
                chunking_rule_id=config.chunking_rule_id,
                corpus_kind=RagCorpusKind(config.corpus_kind),
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
        options = RagConfigOptions.model_validate(
            rag_config_create.options or {}
        ).model_dump(mode="json")
        vector_store = await self.repository.get_vector_store(
            rag_config_create.vector_store_id,
            tenant_id=tenant_id,
        )
        if vector_store is None:
            raise NotFoundServiceException(message="vector_store_not_found")
        config_model = await self.repository.create_rag_config(
            tenant_id=tenant_id,
            source_version_id=rag_config_create.source_version_id,
            vector_store_id=rag_config_create.vector_store_id,
            chunking_rule_id=rag_config_create.chunking_rule_id,
            corpus_kind=rag_config_create.corpus_kind.value,
            options=options,
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
            chunking_rule_id=config_model.chunking_rule_id,
            corpus_kind=RagCorpusKind(config_model.corpus_kind),
            options=config_model.options,
            status=config_model.status,
            version_major=config_model.version_major,
            version_minor=config_model.version_minor,
            version_patch=config_model.version_patch,
            config_hash=config_model.config_hash,
        )

    async def validate_rag_config(
        self,
        *,
        tenant_id: UUID,
        rag_config_id: str,
        principal_id: str,
    ) -> RagConfig:
        config_uuid = UUID(rag_config_id)
        config = await self.repository.get_rag_config(config_uuid)
        if config is None or config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="rag_config_not_found")
        if config.status != VersionStatus.DRAFT:
            raise ResourceBlockedServiceException(message="rag_config_not_draft")
        await self.repository.set_rag_config_status(
            rag_config_id=config_uuid, status=VersionStatus.VALIDATED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CONFIG,
            resource_id=config_uuid,
            version_id=None,
            event_type=AuthoringEventType.RAG_CONFIG_VALIDATED,
            change_type=ChangeType.UPDATE,
            principal_id=principal_id,
            justification="validate rag config",
            schema_version=1,
        )
        refreshed = await self.repository.get_rag_config(config_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="rag_config_not_found")
        return RagConfig(
            id=refreshed.rag_config_id,
            vector_store_id=refreshed.vector_store_id,
            chunking_rule_id=refreshed.chunking_rule_id,
            corpus_kind=RagCorpusKind(refreshed.corpus_kind),
            options=refreshed.options,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
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
            chunking_rule_id=refreshed.chunking_rule_id,
            corpus_kind=RagCorpusKind(refreshed.corpus_kind),
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
            chunking_rule_id=refreshed.chunking_rule_id,
            corpus_kind=RagCorpusKind(refreshed.corpus_kind),
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
            chunking_rule_id=refreshed.chunking_rule_id,
            corpus_kind=RagCorpusKind(refreshed.corpus_kind),
            options=refreshed.options,
            status=refreshed.status,
            version_major=refreshed.version_major,
            version_minor=refreshed.version_minor,
            version_patch=refreshed.version_patch,
            config_hash=refreshed.config_hash,
        )

    async def list_chunking_rules(
        self, *, tenant_id: UUID, limit: int = 200
    ) -> list[RagChunkingRule]:
        rows = await self.repository.list_chunking_rules(
            tenant_id=tenant_id, limit=limit
        )
        return [self._chunking_rule_to_schema(r) for r in rows]

    async def create_chunking_rule(
        self,
        *,
        tenant_id: UUID,
        payload: RagChunkingRuleCreate,
        principal_id: str,
    ) -> RagChunkingRule:
        raw_params = dict(payload.params or {})
        raw_params["strategy"] = payload.strategy.value
        parse_rag_chunking_rule_params(raw_params)
        created = await self.repository.create_chunking_rule(
            tenant_id=tenant_id,
            name=payload.name,
            status=payload.status.value,
            strategy=payload.strategy.value,
            params=payload.params or {},
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CHUNKING_RULE,
            resource_id=created.rag_chunking_rule_id,
            version_id=None,
            event_type=AuthoringEventType.RAG_CHUNKING_RULE_CREATED,
            change_type=ChangeType.CREATE,
            principal_id=principal_id,
            justification="create rag chunking rule",
            schema_version=1,
        )
        return self._chunking_rule_to_schema(created)

    async def update_chunking_rule(
        self,
        *,
        tenant_id: UUID,
        rag_chunking_rule_id: str,
        payload: RagChunkingRuleUpdate,
        principal_id: str,
        change_request: ChangeRequest,
    ) -> RagChunkingRule:
        rule_uuid = UUID(rag_chunking_rule_id)
        existing = await self.repository.get_chunking_rule(
            tenant_id=tenant_id,
            rag_chunking_rule_id=rule_uuid,
        )
        if existing is None:
            raise NotFoundServiceException(message="rag_chunking_rule_not_found")
        next_strategy = (
            payload.strategy.value
            if payload.strategy is not None
            else existing.strategy
        )
        next_params = (
            payload.params if payload.params is not None else existing.params or {}
        )
        raw_validate = dict(next_params)
        raw_validate["strategy"] = next_strategy
        parse_rag_chunking_rule_params(raw_validate)
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        updated = await self.repository.update_chunking_rule(
            tenant_id=tenant_id,
            rag_chunking_rule_id=rule_uuid,
            name=payload.name,
            status=payload.status.value if payload.status is not None else None,
            strategy=payload.strategy.value if payload.strategy is not None else None,
            params=payload.params,
        )
        if updated is None:
            raise NotFoundServiceException(message="rag_chunking_rule_not_found")
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type=ResourceType.RAG_CHUNKING_RULE,
            resource_id=rule_uuid,
            version_id=None,
            event_type=AuthoringEventType.RAG_CHUNKING_RULE_UPDATED,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        return self._chunking_rule_to_schema(updated)

    @staticmethod
    def _chunking_rule_to_schema(row: object) -> RagChunkingRule:
        return RagChunkingRule(
            id=row.rag_chunking_rule_id,
            name=row.name,
            status=row.status,
            strategy=row.strategy,
            params=row.params or {},
            config_hash=row.config_hash,
        )
