from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.ai_policy.repositories.ai_repository import AIRepository
from domain.ai_policy.schemas.ai import (
    AIExecutionPolicyCreate,
    AIExecutionPolicyVersionCreate,
)
from domain.ai_policy.services.ai_service import AIService
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class TestAIService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=AIRepository)
        repo.get_ai_execution_policy = AsyncMock(return_value=None)
        repo.get_ai_execution_policy_version = AsyncMock(return_value=None)
        repo.get_model = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock()
        events.append_event = AsyncMock()
        return events

    @pytest.fixture
    def ai_service(self, repository, authoring_events):
        return AIService(repository=repository, authoring_events=authoring_events)

    @pytest.mark.asyncio
    async def test_create_ai_execution_policy_creates_policy_with_success(
        self, ai_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        policy_create = AIExecutionPolicyCreate(description="Test Policy")
        principal_id = "user-123"

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, description="Test Policy"
        )
        repository.create_ai_execution_policy = AsyncMock(return_value=mock_policy)

        result = await ai_service.create_ai_execution_policy(
            tenant_id=tenant_id,
            ai_execution_policy_create=policy_create,
            principal_id=principal_id,
        )

        assert result.id == policy_id
        assert result.description == "Test Policy"
        repository.create_ai_execution_policy.assert_called_once_with(
            tenant_id=tenant_id, description="Test Policy", created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["tenant_id"] == tenant_id
        assert call_args["resource_type"] == "ai_execution_policy"
        assert call_args["resource_id"] == policy_id
        assert call_args["event_type"] == "AI_EXECUTION_POLICY_CREATED"

    @pytest.mark.asyncio
    async def test_create_ai_execution_policy_version_creates_version_with_success(
        self, ai_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        model_id = uuid4()
        policy_create = AIExecutionPolicyVersionCreate(
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            source_version_id=None,
        )
        principal_id = "user-123"

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_model = SimpleNamespace(model_id=model_id)
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status="DRAFT",
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_model = AsyncMock(return_value=mock_model)
        repository.create_ai_execution_policy_version = AsyncMock(
            return_value=mock_version
        )

        result = await ai_service.create_ai_execution_policy_version(
            tenant_id=tenant_id,
            ai_execution_policy_version_create=policy_create,
            principal_id=principal_id,
        )

        assert result.id == version_id
        assert result.ai_execution_policy_id == policy_id
        assert result.model_id == model_id
        repository.get_ai_execution_policy.assert_called_once_with(policy_id)
        repository.get_model.assert_called_once_with(model_id)
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "AI_EXECUTION_POLICY_VERSION_CREATED"

    @pytest.mark.asyncio
    async def test_create_ai_execution_policy_version_raises_when_policy_not_found(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        model_id = uuid4()
        policy_create = AIExecutionPolicyVersionCreate(
            ai_execution_policy_id=policy_id, model_id=model_id
        )

        repository.get_ai_execution_policy = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="ai_execution_policy_not_found"):
            await ai_service.create_ai_execution_policy_version(
                tenant_id=tenant_id,
                ai_execution_policy_version_create=policy_create,
                principal_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_create_ai_execution_policy_version_raises_when_tenant_mismatch(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        policy_id = uuid4()
        model_id = uuid4()
        policy_create = AIExecutionPolicyVersionCreate(
            ai_execution_policy_id=policy_id, model_id=model_id
        )

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=other_tenant_id
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)

        with pytest.raises(NotFoundServiceException, match="ai_execution_policy_not_found"):
            await ai_service.create_ai_execution_policy_version(
                tenant_id=tenant_id,
                ai_execution_policy_version_create=policy_create,
                principal_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_list_models_returns_empty_list_when_no_results(
        self, ai_service, repository
    ):
        repository.list_models = AsyncMock(return_value=[])

        result = await ai_service.list_models()

        assert result == []
        repository.list_models.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_models_returns_models(self, ai_service, repository):
        model_id = uuid4()
        mock_model = SimpleNamespace(model_id=model_id, name="gpt-4")
        repository.list_models = AsyncMock(return_value=[mock_model])

        result = await ai_service.list_models()

        assert len(result) == 1
        assert result[0].id == model_id
        assert result[0].name == "gpt-4"

    @pytest.mark.asyncio
    async def test_list_ai_execution_policy_versions_returns_empty_list_when_no_results(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.list_ai_execution_policy_versions = AsyncMock(return_value=[])

        result = await ai_service.list_ai_execution_policy_versions(
            tenant_id=tenant_id, ai_execution_policy_id=str(policy_id)
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_list_ai_execution_policy_versions_raises_when_policy_not_found(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        repository.get_ai_execution_policy = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="ai_execution_policy_not_found"):
            await ai_service.list_ai_execution_policy_versions(
                tenant_id=tenant_id, ai_execution_policy_id=str(policy_id)
            )

    @pytest.mark.asyncio
    async def test_publish_ai_execution_policy_version_publishes_with_success(
        self, ai_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        model_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Ready for production")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status=VersionStatus.VALIDATED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_published_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status=VersionStatus.PUBLISHED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)
        repository.set_ai_execution_policy_version_status = AsyncMock()
        repository.get_ai_execution_policy_version = AsyncMock(
            return_value=mock_published_version
        )

        result = await ai_service.publish_ai_execution_policy_version(
            tenant_id=tenant_id,
            ai_execution_policy_id=str(policy_id),
            ai_execution_policy_version_id=str(version_id),
            principal_id="user-123",
            change_request=change_request,
        )

        assert result.status == VersionStatus.PUBLISHED
        repository.set_ai_execution_policy_version_status.assert_called_once_with(
            ai_execution_policy_version_id=version_id, status=VersionStatus.PUBLISHED
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "VERSION_PUBLISHED"

    @pytest.mark.asyncio
    async def test_publish_ai_execution_policy_version_raises_when_not_validated(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Ready")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="ai_execution_policy_version_not_validated",
        ):
            await ai_service.publish_ai_execution_policy_version(
                tenant_id=tenant_id,
                ai_execution_policy_id=str(policy_id),
                ai_execution_policy_version_id=str(version_id),
                principal_id="user-123",
                change_request=change_request,
            )

    @pytest.mark.asyncio
    async def test_deprecate_ai_execution_policy_version_deprecates_with_success(
        self, ai_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        model_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Replaced by v2")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status=VersionStatus.PUBLISHED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_deprecated_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status=VersionStatus.DEPRECATED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)
        repository.set_ai_execution_policy_version_status = AsyncMock()
        repository.get_ai_execution_policy_version = AsyncMock(
            return_value=mock_deprecated_version
        )

        result = await ai_service.deprecate_ai_execution_policy_version(
            tenant_id=tenant_id,
            ai_execution_policy_id=str(policy_id),
            ai_execution_policy_version_id=str(version_id),
            principal_id="user-123",
            change_request=change_request,
        )

        assert result.status == VersionStatus.DEPRECATED
        repository.set_ai_execution_policy_version_status.assert_called_once_with(
            ai_execution_policy_version_id=version_id, status=VersionStatus.DEPRECATED
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "VERSION_DEPRECATED"

    @pytest.mark.asyncio
    async def test_deprecate_ai_execution_policy_version_raises_when_not_published(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Replace")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="ai_execution_policy_version_not_published",
        ):
            await ai_service.deprecate_ai_execution_policy_version(
                tenant_id=tenant_id,
                ai_execution_policy_id=str(policy_id),
                ai_execution_policy_version_id=str(version_id),
                principal_id="user-123",
                change_request=change_request,
            )

    @pytest.mark.asyncio
    async def test_disable_ai_execution_policy_version_disables_with_success(
        self, ai_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        model_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Security issue")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status=VersionStatus.PUBLISHED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        mock_disabled_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            model_id=model_id,
            status=VersionStatus.DISABLED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)
        repository.set_ai_execution_policy_version_status = AsyncMock()
        repository.get_ai_execution_policy_version = AsyncMock(
            return_value=mock_disabled_version
        )

        result = await ai_service.disable_ai_execution_policy_version(
            tenant_id=tenant_id,
            ai_execution_policy_id=str(policy_id),
            ai_execution_policy_version_id=str(version_id),
            principal_id="user-123",
            change_request=change_request,
        )

        assert result.status == VersionStatus.DISABLED
        repository.set_ai_execution_policy_version_status.assert_called_once_with(
            ai_execution_policy_version_id=version_id, status=VersionStatus.DISABLED
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["event_type"] == "VERSION_DISABLED"

    @pytest.mark.asyncio
    async def test_disable_ai_execution_policy_version_raises_when_invalid_status(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="Disable")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)

        with pytest.raises(
            ResourceBlockedServiceException,
            match="ai_execution_policy_version_not_published_or_deprecated",
        ):
            await ai_service.disable_ai_execution_policy_version(
                tenant_id=tenant_id,
                ai_execution_policy_id=str(policy_id),
                ai_execution_policy_version_id=str(version_id),
                principal_id="user-123",
                change_request=change_request,
            )

    @pytest.mark.asyncio
    async def test_publish_ai_execution_policy_version_raises_when_justification_empty(
        self, ai_service, repository
    ):
        tenant_id = uuid4()
        policy_id = uuid4()
        version_id = uuid4()
        change_request = ChangeRequest(change_type="UPDATE", justification="   ")

        mock_policy = SimpleNamespace(
            ai_execution_policy_id=policy_id, tenant_id=tenant_id
        )
        mock_version = SimpleNamespace(
            ai_execution_policy_version_id=version_id,
            ai_execution_policy_id=policy_id,
            status=VersionStatus.VALIDATED,
        )
        repository.get_ai_execution_policy = AsyncMock(return_value=mock_policy)
        repository.get_ai_execution_policy_version = AsyncMock(return_value=mock_version)

        with pytest.raises(DomainValidationException, match="justification_required"):
            await ai_service.publish_ai_execution_policy_version(
                tenant_id=tenant_id,
                ai_execution_policy_id=str(policy_id),
                ai_execution_policy_version_id=str(version_id),
                principal_id="user-123",
                change_request=change_request,
            )
