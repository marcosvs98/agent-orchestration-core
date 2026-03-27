from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.rag.repositories.rag_repository import RagRepository
from domain.rag.schemas.rag import RagConfigCreate, RagCorpusKind
from domain.rag.services.rag_service import RagService
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class TestRagService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=RagRepository)
        repo.get_rag_config = AsyncMock(return_value=None)
        repo.get_vector_store = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock()
        events.append_event = AsyncMock()
        return events

    @pytest.fixture
    def rag_service(self, repository, authoring_events):
        return RagService(repository=repository, authoring_events=authoring_events)

    @pytest.mark.asyncio
    async def test_list_vector_stores_returns_empty_list_when_no_results(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        repository.list_vector_stores = AsyncMock(return_value=[])

        result = await rag_service.list_vector_stores(tenant_id=tenant_id)

        assert result == []
        repository.list_vector_stores.assert_called_once_with(tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_list_vector_stores_returns_stores(self, rag_service, repository):
        tenant_id = uuid4()
        store_id = uuid4()
        mock_store = SimpleNamespace(
            vector_store_id=store_id,
            name="Pinecone",
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536,
            metric="cosine",
            version=1,
            active=True,
        )
        repository.list_vector_stores = AsyncMock(return_value=[mock_store])

        result = await rag_service.list_vector_stores(tenant_id=tenant_id)

        assert len(result) == 1
        assert result[0].id == store_id
        assert result[0].name == "Pinecone"

    @pytest.mark.asyncio
    async def test_list_rag_configs_returns_empty_list_when_no_results(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        repository.list_rag_configs = AsyncMock(return_value=[])

        result = await rag_service.list_rag_configs(
            tenant_id=tenant_id, status_filter=None, limit=200
        )

        assert result == []
        repository.list_rag_configs.assert_called_once_with(
            tenant_id=tenant_id, status_filter=None, limit=200
        )

    @pytest.mark.asyncio
    async def test_list_rag_configs_returns_configs(self, rag_service, repository):
        tenant_id = uuid4()
        config_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status="DRAFT",
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.list_rag_configs = AsyncMock(return_value=[mock_config])

        result = await rag_service.list_rag_configs(
            tenant_id=tenant_id, status_filter=["DRAFT"], limit=200
        )

        assert len(result) == 1
        assert result[0].id == config_id
        assert result[0].vector_store_id == vector_store_id
        assert result[0].status == "DRAFT"

    @pytest.mark.asyncio
    async def test_create_rag_config_creates_config_with_success(
        self, rag_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        config_create = RagConfigCreate(
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind=RagCorpusKind.TENANT_KNOWLEDGE,
            options={"chunk_size": 512},
        )
        principal_id = "user-123"

        mock_vector_store = SimpleNamespace(vector_store_id=vector_store_id)
        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status="DRAFT",
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_vector_store = AsyncMock(return_value=mock_vector_store)
        repository.create_rag_config = AsyncMock(return_value=mock_config)

        result = await rag_service.create_rag_config(
            tenant_id=tenant_id,
            rag_config_create=config_create,
            principal_id=principal_id,
        )

        assert result.id == config_id
        assert result.vector_store_id == vector_store_id
        assert result.options == {"chunk_size": 512}
        repository.get_vector_store.assert_called_once_with(
            vector_store_id,
            tenant_id=tenant_id,
        )
        repository.create_rag_config.assert_called_once()
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["tenant_id"] == tenant_id
        assert call_args["resource_type"] == "rag_config"
        assert call_args["resource_id"] == config_id
        assert call_args["event_type"] == "RAG_CONFIG_CREATED"

    @pytest.mark.asyncio
    async def test_create_rag_config_raises_when_vector_store_not_found(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        config_create = RagConfigCreate(
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind=RagCorpusKind.TENANT_KNOWLEDGE,
        )
        principal_id = "user-123"

        repository.get_vector_store = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="vector_store_not_found"):
            await rag_service.create_rag_config(
                tenant_id=tenant_id,
                rag_config_create=config_create,
                principal_id=principal_id,
            )

    @pytest.mark.asyncio
    async def test_publish_rag_config_publishes_with_success(
        self, rag_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Ready for production")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status=VersionStatus.VALIDATED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_published_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status=VersionStatus.PUBLISHED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_rag_config = AsyncMock(
            side_effect=[mock_config, mock_published_config]
        )
        repository.set_rag_config_status = AsyncMock()

        result = await rag_service.publish_rag_config(
            tenant_id=tenant_id,
            rag_config_id=str(config_id),
            principal_id="user-123",
            change_request=change_request,
        )

        assert result.status == VersionStatus.PUBLISHED
        repository.set_rag_config_status.assert_called_once_with(
            rag_config_id=config_id, status=VersionStatus.PUBLISHED
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "RAG_CONFIG_PUBLISHED"

    @pytest.mark.asyncio
    async def test_publish_rag_config_raises_when_not_validated(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Ready")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_rag_config = AsyncMock(return_value=mock_config)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="rag_config_not_validated",
        ):
            await rag_service.publish_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
                change_request=change_request,
            )

    @pytest.mark.asyncio
    async def test_validate_rag_config_sets_validated(
        self, rag_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        mock_draft = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={},
            status=VersionStatus.DRAFT,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_validated = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={},
            status=VersionStatus.VALIDATED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_rag_config = AsyncMock(
            side_effect=[mock_draft, mock_validated]
        )
        repository.set_rag_config_status = AsyncMock()

        result = await rag_service.validate_rag_config(
            tenant_id=tenant_id,
            rag_config_id=str(config_id),
            principal_id="user-123",
        )

        assert result.status == VersionStatus.VALIDATED
        repository.set_rag_config_status.assert_called_once_with(
            rag_config_id=config_id, status=VersionStatus.VALIDATED
        )
        authoring_events.append_event.assert_called_once()
        assert (
            authoring_events.append_event.call_args[1]["event_type"]
            == "RAG_CONFIG_VALIDATED"
        )

    @pytest.mark.asyncio
    async def test_validate_rag_config_raises_when_not_draft(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            status=VersionStatus.VALIDATED,
        )
        repository.get_rag_config = AsyncMock(return_value=mock_config)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="rag_config_not_draft",
        ):
            await rag_service.validate_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_validate_rag_config_raises_when_not_found(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        repository.get_rag_config = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="rag_config_not_found"):
            await rag_service.validate_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_validate_rag_config_raises_when_wrong_tenant(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        other_tenant = uuid4()
        config_id = uuid4()
        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=other_tenant,
            status=VersionStatus.DRAFT,
        )
        repository.get_rag_config = AsyncMock(return_value=mock_config)

        with pytest.raises(NotFoundServiceException, match="rag_config_not_found"):
            await rag_service.validate_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_deprecate_rag_config_deprecates_with_success(
        self, rag_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Replaced by v2")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status=VersionStatus.PUBLISHED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_deprecated_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status=VersionStatus.DEPRECATED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_rag_config = AsyncMock(
            side_effect=[mock_config, mock_deprecated_config]
        )
        repository.set_rag_config_status = AsyncMock()

        result = await rag_service.deprecate_rag_config(
            tenant_id=tenant_id,
            rag_config_id=str(config_id),
            principal_id="user-123",
            change_request=change_request,
        )

        assert result.status == VersionStatus.DEPRECATED
        repository.set_rag_config_status.assert_called_once_with(
            rag_config_id=config_id, status=VersionStatus.DEPRECATED
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "RAG_CONFIG_DEPRECATED"

    @pytest.mark.asyncio
    async def test_deprecate_rag_config_raises_when_not_published(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Replace")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_rag_config = AsyncMock(return_value=mock_config)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="rag_config_not_published",
        ):
            await rag_service.deprecate_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
                change_request=change_request,
            )

    @pytest.mark.asyncio
    async def test_disable_rag_config_disables_with_success(
        self, rag_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        vector_store_id = uuid4()
        chunking_rule_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Security issue")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status=VersionStatus.PUBLISHED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_disabled_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            vector_store_id=vector_store_id,
            chunking_rule_id=chunking_rule_id,
            corpus_kind="TENANT_KNOWLEDGE",
            options={"chunk_size": 512},
            status=VersionStatus.DISABLED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_rag_config = AsyncMock(
            side_effect=[mock_config, mock_disabled_config]
        )
        repository.set_rag_config_status = AsyncMock()

        result = await rag_service.disable_rag_config(
            tenant_id=tenant_id,
            rag_config_id=str(config_id),
            principal_id="user-123",
            change_request=change_request,
        )

        assert result.status == VersionStatus.DISABLED
        repository.set_rag_config_status.assert_called_once_with(
            rag_config_id=config_id, status=VersionStatus.DISABLED
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "RAG_CONFIG_DISABLED"

    @pytest.mark.asyncio
    async def test_disable_rag_config_raises_when_invalid_status(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Disable")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_rag_config = AsyncMock(return_value=mock_config)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="rag_config_not_published_or_deprecated",
        ):
            await rag_service.disable_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
                change_request=change_request,
            )

    @pytest.mark.asyncio
    async def test_publish_rag_config_raises_when_justification_empty(
        self, rag_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="   ")

        mock_config = SimpleNamespace(
            rag_config_id=config_id,
            tenant_id=tenant_id,
            status=VersionStatus.VALIDATED,
        )
        repository.get_rag_config = AsyncMock(return_value=mock_config)

        with pytest.raises(DomainValidationException, match="justification_required"):
            await rag_service.publish_rag_config(
                tenant_id=tenant_id,
                rag_config_id=str(config_id),
                principal_id="user-123",
                change_request=change_request,
            )
