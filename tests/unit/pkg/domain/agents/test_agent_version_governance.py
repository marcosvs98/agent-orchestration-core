from types import SimpleNamespace
from uuid import uuid4

import pytest

from domain.agents.services.agents_service import AgentsService
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from exceptions.service_exceptions import ResourceBlockedServiceException


@pytest.mark.asyncio
async def test_publish_agent_version_requires_validated(mocker):
    tenant_id = uuid4()
    principal_id = "p"
    agent_id = uuid4()
    agent_version_id = uuid4()

    agents_repo = mocker.Mock()
    agents_repo.get_agent = mocker.AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repo.get_agent_version = mocker.AsyncMock(
        return_value=SimpleNamespace(agent_id=agent_id, status=VersionStatus.DRAFT)
    )

    authoring_events = mocker.Mock()
    authoring_events.append_event = mocker.AsyncMock()

    service = AgentsService(repository=agents_repo, authoring_events=authoring_events)

    with pytest.raises(ResourceBlockedServiceException, match="agent_version_not_validated"):
        await service.publish_agent_version(
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_version_id=agent_version_id,
            principal_id=principal_id,
            change_request=ChangeRequest(change_type="agent", justification="j"),
        )


@pytest.mark.asyncio
async def test_activate_and_rollback_emit_authoring_events(mocker):
    tenant_id = uuid4()
    principal_id = "principal"
    agent_id = uuid4()
    agent_version_id = uuid4()

    agents_repo = mocker.Mock()
    agents_repo.get_agent = mocker.AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    agents_repo.get_agent_version = mocker.AsyncMock(
        return_value=SimpleNamespace(agent_id=agent_id, status=VersionStatus.PUBLISHED)
    )
    agents_repo.upsert_active_agent_version = mocker.AsyncMock()

    authoring_events = mocker.Mock()
    authoring_events.append_event = mocker.AsyncMock()

    service = AgentsService(repository=agents_repo, authoring_events=authoring_events)

    await service.activate_agent_version(
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        principal_id=principal_id,
        change_request=ChangeRequest(change_type="activate", justification="activate"),
    )
    await service.rollback_agent_version(
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        principal_id=principal_id,
        change_request=ChangeRequest(change_type="rollback", justification="rollback"),
    )

    event_types = [c.kwargs["event_type"] for c in authoring_events.append_event.call_args_list]
    assert "VERSION_ACTIVATED" in event_types
    assert "VERSION_ROLLED_BACK" in event_types
