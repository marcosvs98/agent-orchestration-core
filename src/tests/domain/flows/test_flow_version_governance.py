from types import SimpleNamespace
from uuid import uuid4

import pytest

from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.flows.services.flows_service import FlowsService
from exceptions.service_exceptions import ResourceBlockedServiceException


@pytest.mark.asyncio
async def test_validate_flow_version_sets_validated_status(mocker):
    tenant_id = uuid4()
    flow_id = uuid4()
    flow_version_id = uuid4()

    flows_repo = mocker.Mock()
    flows_repo.get_flow = mocker.AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    flows_repo.get_flow_version = mocker.AsyncMock(
        side_effect=[
            SimpleNamespace(flow_id=flow_id, status=VersionStatus.DRAFT),
            SimpleNamespace(
                flow_version_id=flow_version_id,
                flow_id=flow_id,
                status=VersionStatus.VALIDATED,
                version_major=1,
                version_minor=0,
                version_patch=0,
                config_hash=None,
                min_agent_version_major=None,
                min_agent_version_minor=None,
                min_agent_version_patch=None,
            ),
        ]
    )
    flows_repo.list_nodes_for_flow_version = mocker.AsyncMock(
        return_value=[SimpleNamespace(node_id=uuid4())]
    )
    flows_repo.list_routing_rules_for_flow_version = mocker.AsyncMock(return_value=[])
    flows_repo.set_flow_version_status = mocker.AsyncMock()
    flows_repo.get_flow_graph_draft = mocker.AsyncMock(
        return_value=SimpleNamespace(status="VALIDATED")
    )

    policy_repo = mocker.Mock()
    policy_repo.get_default_policy_for_tenant = mocker.AsyncMock(
        return_value=SimpleNamespace(execution_limit_policy_id=uuid4())
    )
    policy_repo.get_published_policy_version = mocker.AsyncMock(
        return_value=SimpleNamespace(execution_limit_policy_version_id=uuid4())
    )

    authoring_events = mocker.Mock()
    authoring_events.append_event = mocker.AsyncMock()

    service = FlowsService(
        repository=flows_repo,
        limit_policy_repository=policy_repo,
        authoring_events=authoring_events,
    )

    result = await service.validate_flow_version(
        tenant_id=tenant_id, flow_id=str(flow_id), flow_version_id=str(flow_version_id)
    )

    assert result.status == VersionStatus.VALIDATED
    flows_repo.set_flow_version_status.assert_called_once()


@pytest.mark.asyncio
async def test_publish_flow_version_requires_validated(mocker):
    tenant_id = uuid4()
    principal_id = "p"
    flow_id = uuid4()
    flow_version_id = uuid4()

    flows_repo = mocker.Mock()
    flows_repo.get_flow = mocker.AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    flows_repo.get_flow_version = mocker.AsyncMock(
        return_value=SimpleNamespace(flow_id=flow_id, status=VersionStatus.DRAFT)
    )

    policy_repo = mocker.Mock()
    authoring_events = mocker.Mock()
    authoring_events.append_event = mocker.AsyncMock()

    service = FlowsService(
        repository=flows_repo,
        limit_policy_repository=policy_repo,
        authoring_events=authoring_events,
    )

    with pytest.raises(ResourceBlockedServiceException, match="flow_version_not_validated"):
        await service.publish_flow_version(
            tenant_id=tenant_id,
            flow_id=str(flow_id),
            flow_version_id=str(flow_version_id),
            principal_id=principal_id,
            change_request=ChangeRequest(change_type="flow", justification="j"),
        )


@pytest.mark.asyncio
async def test_activate_and_rollback_emit_authoring_events(mocker):
    tenant_id = uuid4()
    principal_id = "principal"
    flow_id = uuid4()
    published_version_id = uuid4()

    flows_repo = mocker.Mock()
    flows_repo.get_flow = mocker.AsyncMock(return_value=SimpleNamespace(tenant_id=tenant_id))
    flows_repo.get_flow_version = mocker.AsyncMock(
        return_value=SimpleNamespace(flow_id=flow_id, status=VersionStatus.PUBLISHED)
    )
    flows_repo.upsert_active_flow_version = mocker.AsyncMock()
    flows_repo.get_flow_graph_snapshot_by_flow_version = mocker.AsyncMock(
        return_value=SimpleNamespace(flow_graph_snapshot_id=uuid4())
    )

    policy_repo = mocker.Mock()

    authoring_events = mocker.Mock()
    authoring_events.append_event = mocker.AsyncMock()

    service = FlowsService(
        repository=flows_repo,
        limit_policy_repository=policy_repo,
        authoring_events=authoring_events,
    )

    await service.activate_flow_version(
        tenant_id=tenant_id,
        flow_id=str(flow_id),
        flow_version_id=str(published_version_id),
        principal_id=principal_id,
        change_request=ChangeRequest(change_type="activate", justification="activate"),
    )

    await service.rollback_flow_version(
        tenant_id=tenant_id,
        flow_id=str(flow_id),
        flow_version_id=str(published_version_id),
        principal_id=principal_id,
        change_request=ChangeRequest(change_type="rollback", justification="rollback"),
    )

    event_types = [c.kwargs["event_type"] for c in authoring_events.append_event.call_args_list]
    assert "VERSION_ACTIVATED" in event_types
    assert "VERSION_ROLLED_BACK" in event_types
