from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.onboarding.repositories.onboarding_repository import OnboardingRepository
from domain.onboarding.schemas.onboarding import (
    OnboardingCreate,
    OnboardingRunCreate,
)
from domain.onboarding.services.onboarding_service import OnboardingService
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)


class TestOnboardingService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=OnboardingRepository)
        repo.get_onboarding = AsyncMock(return_value=None)
        repo.get_onboarding_version = AsyncMock(return_value=None)
        repo.get_onboarding_run = AsyncMock(return_value=None)
        repo.get_step = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock()
        events.append_event = AsyncMock()
        return events

    @pytest.fixture
    def onboarding_service(self, repository, authoring_events):
        return OnboardingService(repository=repository, authoring_events=authoring_events)

    @pytest.mark.asyncio
    async def test_list_onboardings_returns_empty_list_when_no_results(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        repository.list_onboardings = AsyncMock(return_value=[])

        result = await onboarding_service.list_onboardings(tenant_id=tenant_id, limit=200)

        assert result == []
        repository.list_onboardings.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_list_onboardings_returns_onboardings_filtered_by_tenant(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        mock_onboarding = SimpleNamespace(
            onboarding_id=onboarding_id, name="Test Onboarding", created_by="user-123"
        )
        repository.list_onboardings = AsyncMock(return_value=[mock_onboarding])

        result = await onboarding_service.list_onboardings(tenant_id=tenant_id, limit=200)

        assert len(result) == 1
        assert result[0].id == onboarding_id
        assert result[0].name == "Test Onboarding"
        assert result[0].created_by == "user-123"
        repository.list_onboardings.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_create_onboarding_creates_onboarding_with_success(
        self, onboarding_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        onboarding_create = OnboardingCreate(name="New Onboarding")
        principal_id = "user-123"

        mock_onboarding = SimpleNamespace(
            onboarding_id=onboarding_id, name="New Onboarding", created_by=principal_id
        )
        repository.create_onboarding = AsyncMock(return_value=mock_onboarding)

        result = await onboarding_service.create_onboarding(
            tenant_id=tenant_id,
            onboarding_create=onboarding_create,
            principal_id=principal_id,
        )

        assert result.id == onboarding_id
        assert result.name == "New Onboarding"
        assert result.created_by == principal_id
        repository.create_onboarding.assert_called_once_with(
            tenant_id=tenant_id, name="New Onboarding", created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["tenant_id"] == tenant_id
        assert call_args["resource_type"] == "onboarding"
        assert call_args["resource_id"] == onboarding_id
        assert call_args["event_type"] == "ONBOARDING_CREATED"
        assert call_args["change_type"] == "CREATE"
        assert call_args["principal_id"] == principal_id

    @pytest.mark.asyncio
    async def test_list_onboarding_versions_returns_empty_list_when_no_results(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.list_onboarding_versions = AsyncMock(return_value=[])

        result = await onboarding_service.list_onboarding_versions(
            tenant_id=tenant_id, onboarding_id=str(onboarding_id)
        )

        assert result == []
        repository.get_onboarding.assert_called_once_with(onboarding_id)
        repository.list_onboarding_versions.assert_called_once_with(onboarding_id)

    @pytest.mark.asyncio
    async def test_list_onboarding_versions_raises_when_onboarding_not_found(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        repository.get_onboarding = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="onboarding_not_found"):
            await onboarding_service.list_onboarding_versions(
                tenant_id=tenant_id, onboarding_id=str(onboarding_id)
            )

    @pytest.mark.asyncio
    async def test_list_onboarding_versions_raises_when_tenant_mismatch(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        onboarding_id = uuid4()
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=other_tenant_id)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)

        with pytest.raises(NotFoundServiceException, match="onboarding_not_found"):
            await onboarding_service.list_onboarding_versions(
                tenant_id=tenant_id, onboarding_id=str(onboarding_id)
            )

    @pytest.mark.asyncio
    async def test_create_onboarding_run_creates_run_with_success(
        self, onboarding_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()
        onboarding_run_create = OnboardingRunCreate(onboarding_version_id=version_id)
        principal_id = "user-123"

        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.create_onboarding_run = AsyncMock(return_value=mock_run)

        result = await onboarding_service.create_onboarding_run(
            tenant_id=tenant_id,
            onboarding_run_create=onboarding_run_create,
            principal_id=principal_id,
        )

        assert result.id == run_id
        assert result.onboarding_version_id == version_id
        repository.get_onboarding_version.assert_called_once_with(version_id)
        repository.get_onboarding.assert_called_once_with(onboarding_id)
        repository.create_onboarding_run.assert_called_once_with(
            onboarding_version_id=version_id, created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()
        call_args = authoring_events.append_event.call_args[1]
        assert call_args["tenant_id"] == tenant_id
        assert call_args["resource_type"] == "onboarding_run"
        assert call_args["resource_id"] == run_id
        assert call_args["event_type"] == "ONBOARDING_RUN_CREATED"

    @pytest.mark.asyncio
    async def test_get_onboarding_run_returns_run_with_success(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()

        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        repository.get_onboarding_run = AsyncMock(return_value=mock_run)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)

        result = await onboarding_service.get_onboarding_run(
            tenant_id=tenant_id, onboarding_run_id=str(run_id)
        )

        assert result.id == run_id
        assert result.onboarding_version_id == version_id

    @pytest.mark.asyncio
    async def test_list_steps_returns_empty_list_when_no_results(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()

        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        repository.get_onboarding_run = AsyncMock(return_value=mock_run)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.list_steps = AsyncMock(return_value=[])

        result = await onboarding_service.list_steps(
            tenant_id=tenant_id, onboarding_run_id=str(run_id)
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_current_step_returns_none_when_no_active_step(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()

        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        repository.get_onboarding_run = AsyncMock(return_value=mock_run)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.list_steps = AsyncMock(return_value=[])

        result = await onboarding_service.get_current_step(
            tenant_id=tenant_id, onboarding_run_id=str(run_id)
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_is_run_completed_returns_true_when_all_steps_completed(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()

        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        mock_step1 = SimpleNamespace(status="COMPLETED")
        mock_step2 = SimpleNamespace(status="COMPLETED")
        repository.get_onboarding_run = AsyncMock(return_value=mock_run)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.list_steps = AsyncMock(return_value=[mock_step1, mock_step2])

        result = await onboarding_service.is_run_completed(
            tenant_id=tenant_id, onboarding_run_id=str(run_id)
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_advance_step_updates_status_and_emits_events(
        self, onboarding_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()
        step_id = uuid4()
        step_run_id = uuid4()
        input_payload = {"key": "value"}
        principal_id = "user-123"

        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        mock_step_run = SimpleNamespace(
            step_run_id=step_run_id,
            onboarding_run_id=run_id,
            onboarding_step_id=step_id,
            name="Step 1",
            status="PENDING",
            input_payload={},
            output_payload={},
            schema_id=None,
        )
        mock_updated_step = SimpleNamespace(
            step_run_id=step_run_id,
            onboarding_run_id=run_id,
            onboarding_step_id=step_id,
            name="Step 1",
            status="COMPLETED",
            input_payload=input_payload,
            output_payload={"result": "processed", "input": input_payload},
            schema_id=None,
        )
        repository.get_onboarding_run = AsyncMock(return_value=mock_run)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.get_step = AsyncMock(return_value=mock_step_run)
        repository.update_step_status = AsyncMock(return_value=mock_updated_step)
        repository.list_onboarding_steps = AsyncMock(return_value=[])

        result = await onboarding_service.advance_step(
            tenant_id=tenant_id,
            onboarding_run_id=str(run_id),
            step_run_id=str(step_run_id),
            input_payload=input_payload,
            principal_id=principal_id,
        )

        assert result.status == "COMPLETED"
        assert result.input_payload == input_payload
        assert authoring_events.append_event.call_count == 2
        first_call = authoring_events.append_event.call_args_list[0][1]
        assert first_call["event_type"] == "ONBOARDING_STEP_STARTED"
        second_call = authoring_events.append_event.call_args_list[1][1]
        assert second_call["event_type"] == "ONBOARDING_STEP_COMPLETED"

    @pytest.mark.asyncio
    async def test_advance_step_raises_when_step_not_in_valid_status(
        self, onboarding_service, repository
    ):
        tenant_id = uuid4()
        onboarding_id = uuid4()
        version_id = uuid4()
        run_id = uuid4()
        step_id = uuid4()
        step_run_id = uuid4()
        input_payload = {"key": "value"}

        mock_run = SimpleNamespace(onboarding_run_id=run_id, onboarding_version_id=version_id)
        mock_version = SimpleNamespace(
            onboarding_version_id=version_id, onboarding_id=onboarding_id
        )
        mock_onboarding = SimpleNamespace(onboarding_id=onboarding_id, tenant_id=tenant_id)
        mock_step_run = SimpleNamespace(
            step_run_id=step_run_id,
            onboarding_run_id=run_id,
            onboarding_step_id=step_id,
            status="COMPLETED",
        )
        repository.get_onboarding_run = AsyncMock(return_value=mock_run)
        repository.get_onboarding_version = AsyncMock(return_value=mock_version)
        repository.get_onboarding = AsyncMock(return_value=mock_onboarding)
        repository.get_step = AsyncMock(return_value=mock_step_run)

        with pytest.raises(
            DomainValidationException,
            match="step_run_not_in_valid_status_for_advance",
        ):
            await onboarding_service.advance_step(
                tenant_id=tenant_id,
                onboarding_run_id=str(run_id),
                step_run_id=str(step_run_id),
                input_payload=input_payload,
                principal_id="user-123",
            )
