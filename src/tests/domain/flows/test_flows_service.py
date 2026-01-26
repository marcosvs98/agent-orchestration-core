from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.flows.repositories.flows_repository import FlowsRepository
from domain.flows.schemas.flows import (
    ConditionExpressionCreate,
    FlowCreate,
    FlowVersionCreate,
    NodeCreate,
    RouterCreate,
    RoutingRuleCreate,
)
from domain.flows.services.flows_service import FlowsService
from exceptions.service_exceptions import (
    NotFoundServiceException,
    DomainValidationException,
    ResourceBlockedServiceException,
)
from domain.common.schemas.versioning import VersionStatus


class TestFlowsService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=FlowsRepository)
        repo.get_flow = AsyncMock(return_value=None)
        repo.get_flow_version = AsyncMock(return_value=None)
        repo.get_node = AsyncMock(return_value=None)
        repo.list_nodes_for_flow_version = AsyncMock(return_value=[])
        repo.authoring_events = MagicMock()
        repo.authoring_events.append_event = AsyncMock()
        return repo

    @pytest.fixture
    def limit_policy_repository(self):
        return MagicMock()

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock()
        events.append_event = AsyncMock()
        return events

    @pytest.fixture
    def flows_service(self, repository, limit_policy_repository, authoring_events):
        return FlowsService(
            repository=repository,
            limit_policy_repository=limit_policy_repository,
            authoring_events=authoring_events,
        )

    @pytest.mark.asyncio
    async def test_list_flows_returns_empty_list_when_no_results(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        repository.list_flows = AsyncMock(return_value=[])

        result = await flows_service.list_flows(tenant_id=tenant_id, limit=200)

        assert result == []
        repository.list_flows.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_list_flows_returns_flows_filtered_by_tenant(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        mock_flow = SimpleNamespace(
            flow_id=flow_id,
            name="Test Flow",
            description="Test description",
            tags=["tag1", "tag2"],
            created_by="user-123"
        )
        repository.list_flows = AsyncMock(return_value=[mock_flow])

        result = await flows_service.list_flows(tenant_id=tenant_id, limit=200)

        assert len(result) == 1
        assert result[0].id == flow_id
        assert result[0].name == "Test Flow"
        assert result[0].description == "Test description"
        assert result[0].tags == ["tag1", "tag2"]
        assert result[0].created_by == "user-123"
        repository.list_flows.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_create_flow_creates_flow_with_success(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        flow_create = FlowCreate(name="New Flow")
        principal_id = "user-123"

        mock_flow = SimpleNamespace(
            flow_id=flow_id,
            name="New Flow",
            description=None,
            tags=None,
            created_by=principal_id
        )
        repository.create_flow = AsyncMock(return_value=mock_flow)

        result = await flows_service.create_flow(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )

        assert result.id == flow_id
        assert result.name == "New Flow"
        assert result.description is None
        assert result.tags is None
        assert result.created_by == principal_id
        repository.create_flow.assert_called_once_with(
            tenant_id=tenant_id, name="New Flow", description=None, tags=None, created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_with_description_and_tags(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        flow_create = FlowCreate(
            name="New Flow",
            description="Flow description",
            tags=["tag1", "tag2"]
        )
        principal_id = "user-123"

        mock_flow = SimpleNamespace(
            flow_id=flow_id,
            name="New Flow",
            description="Flow description",
            tags=["tag1", "tag2"],
            created_by=principal_id
        )
        repository.create_flow = AsyncMock(return_value=mock_flow)

        result = await flows_service.create_flow(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )

        assert result.id == flow_id
        assert result.name == "New Flow"
        assert result.description == "Flow description"
        assert result.tags == ["tag1", "tag2"]
        assert result.created_by == principal_id
        repository.create_flow.assert_called_once_with(
            tenant_id=tenant_id,
            name="New Flow",
            description="Flow description",
            tags=["tag1", "tag2"],
            created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_flow_raises_when_name_is_empty(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_create = FlowCreate(name="")
        principal_id = "user-123"

        with pytest.raises(DomainValidationException, match="flow_name_required"):
            await flows_service.create_flow(
                tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
            )

        repository.create_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_flow_raises_when_name_is_only_whitespace(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_create = FlowCreate(name="   ")
        principal_id = "user-123"

        with pytest.raises(DomainValidationException, match="flow_name_required"):
            await flows_service.create_flow(
                tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
            )

        repository.create_flow.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_flow_strips_name_whitespace(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        flow_create = FlowCreate(name="  New Flow  ")
        principal_id = "user-123"

        mock_flow = SimpleNamespace(
            flow_id=flow_id,
            name="New Flow",
            description=None,
            tags=None,
            created_by=principal_id
        )
        repository.create_flow = AsyncMock(return_value=mock_flow)

        result = await flows_service.create_flow(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )

        assert result.id == flow_id
        assert result.name == "New Flow"
        assert result.description is None
        assert result.tags is None
        assert result.created_by == principal_id
        repository.create_flow.assert_called_once_with(
            tenant_id=tenant_id, name="New Flow", description=None, tags=None, created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_flow_returns_flow_when_exists(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        mock_flow = SimpleNamespace(
            flow_id=flow_id,
            tenant_id=tenant_id,
            name="Test Flow",
            description="Test description",
            tags=["tag1"],
            created_by="user-123"
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)

        result = await flows_service.get_flow(tenant_id=tenant_id, flow_id=str(flow_id))

        assert result.id == flow_id
        assert result.name == "Test Flow"
        assert result.description == "Test description"
        assert result.tags == ["tag1"]
        assert result.created_by == "user-123"
        repository.get_flow.assert_called_once_with(flow_id)

    @pytest.mark.asyncio
    async def test_get_flow_raises_when_not_found(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        repository.get_flow = AsyncMock(return_value=None)

        with pytest.raises(NotFoundServiceException, match="flow_not_found"):
            await flows_service.get_flow(tenant_id=tenant_id, flow_id=str(flow_id))

    @pytest.mark.asyncio
    async def test_get_flow_raises_when_tenant_mismatch(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        flow_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=other_tenant_id, name="Test Flow")
        repository.get_flow = AsyncMock(return_value=mock_flow)

        with pytest.raises(NotFoundServiceException, match="flow_not_found"):
            await flows_service.get_flow(tenant_id=tenant_id, flow_id=str(flow_id))

    @pytest.mark.asyncio
    async def test_list_flow_versions_returns_empty_list_when_no_results(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.list_flow_versions = AsyncMock(return_value=[])

        result = await flows_service.list_flow_versions(
            tenant_id=tenant_id, flow_id=str(flow_id), status_filter=None
        )

        assert result == []
        repository.get_flow.assert_called_once_with(flow_id)
        repository.list_flow_versions.assert_called_once_with(
            flow_id=flow_id, status_filter=None
        )

    @pytest.mark.asyncio
    async def test_list_flow_versions_filters_by_status(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status="PUBLISHED",
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
            min_agent_version_major=None,
            min_agent_version_minor=None,
            min_agent_version_patch=None,
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.list_flow_versions = AsyncMock(return_value=[mock_version])

        result = await flows_service.list_flow_versions(
            tenant_id=tenant_id, flow_id=str(flow_id), status_filter=["PUBLISHED"]
        )

        assert len(result) == 1
        assert result[0].id == version_id
        assert result[0].status == "PUBLISHED"
        repository.list_flow_versions.assert_called_once_with(
            flow_id=flow_id, status_filter=["PUBLISHED"]
        )

    @pytest.mark.asyncio
    async def test_create_flow_version_creates_with_provided_version_numbers(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status="DRAFT",
            version_major=2,
            version_minor=1,
            version_patch=0,
            config_hash=None,
            min_agent_version_major=None,
            min_agent_version_minor=None,
            min_agent_version_patch=None,
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.create_flow_version = AsyncMock(return_value=mock_version)
        flow_version_create = FlowVersionCreate(
            version_major=2, version_minor=1, version_patch=0
        )

        result = await flows_service.create_flow_version(
            tenant_id=tenant_id,
            flow_id=str(flow_id),
            flow_version_create=flow_version_create,
            principal_id="user-123",
        )

        assert result.id == version_id
        assert result.version_major == 2
        assert result.version_minor == 1
        assert result.version_patch == 0
        repository.create_flow_version.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_nodes_returns_nodes_for_version(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        node_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(flow_version_id=version_id, flow_id=flow_id)
        mock_node = SimpleNamespace(
            node_id=node_id, flow_version_id=version_id, ai_task_id=None
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.list_nodes_for_flow_version = AsyncMock(return_value=[mock_node])

        result = await flows_service.list_nodes(
            tenant_id=tenant_id, flow_id=str(flow_id), flow_version_id=str(version_id)
        )

        assert len(result) == 1
        assert result[0].id == node_id
        assert result[0].flow_version_id == version_id

    @pytest.mark.asyncio
    async def test_create_node_creates_node_with_success(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        node_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(flow_version_id=version_id, flow_id=flow_id)
        mock_node = SimpleNamespace(
            node_id=node_id, flow_version_id=version_id, ai_task_id=None
        )
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.create_node = AsyncMock(return_value=mock_node)
        node_create = NodeCreate(flow_version_id=version_id, ai_task_id=None)

        result = await flows_service.create_node(
            tenant_id=tenant_id, node_create=node_create, principal_id="user-123"
        )

        assert result.id == node_id
        assert result.flow_version_id == version_id
        repository.create_node.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_routers_returns_routers_filtered_by_tenant(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        router_id = uuid4()
        node_id = uuid4()
        mock_router = SimpleNamespace(router_id=router_id, node_id=node_id)
        repository.list_routers = AsyncMock(return_value=[mock_router])

        result = await flows_service.list_routers(tenant_id=tenant_id, limit=200)

        assert len(result) == 1
        assert result[0].id == router_id
        assert result[0].node_id == node_id
        repository.list_routers.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_create_router_creates_router_with_success(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        node_id = uuid4()
        router_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(flow_version_id=version_id, flow_id=flow_id)
        mock_node = SimpleNamespace(node_id=node_id, flow_version_id=version_id)
        mock_router = SimpleNamespace(router_id=router_id, node_id=node_id)
        repository.get_node = AsyncMock(return_value=mock_node)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.create_router = AsyncMock(return_value=mock_router)
        router_create = RouterCreate(node_id=node_id)

        result = await flows_service.create_router(
            tenant_id=tenant_id, router_create=router_create, principal_id="user-123"
        )

        assert result.id == router_id
        assert result.node_id == node_id
        repository.create_router.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_condition_expression_creates_with_success(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        expr_id = uuid4()
        mock_expr = SimpleNamespace(
            condition_expression_id=expr_id, expression="x > 5"
        )
        repository.create_condition_expression = AsyncMock(return_value=mock_expr)
        expr_create = ConditionExpressionCreate(expression="x > 5")

        result = await flows_service.create_condition_expression(
            tenant_id=tenant_id,
            condition_expression_create=expr_create,
            principal_id="user-123",
        )

        assert result.id == expr_id
        assert result.expression == "x > 5"
        repository.create_condition_expression.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_routing_rule_creates_with_success(
        self, flows_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        router_id = uuid4()
        node_id = uuid4()
        from_node_id = uuid4()
        to_node_id = uuid4()
        condition_expr_id = uuid4()
        rule_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(flow_version_id=version_id, flow_id=flow_id)
        mock_router = SimpleNamespace(router_id=router_id, node_id=node_id)
        mock_router_node = SimpleNamespace(node_id=node_id, flow_version_id=version_id)
        mock_rule = SimpleNamespace(
            routing_rule_id=rule_id,
            router_id=router_id,
            condition_expression_id=condition_expr_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
        )
        repository.get_router = AsyncMock(return_value=mock_router)
        repository.get_node = AsyncMock(return_value=mock_router_node)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.create_routing_rule = AsyncMock(return_value=mock_rule)
        rule_create = RoutingRuleCreate(
            router_id=router_id,
            condition_expression_id=condition_expr_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
        )

        result = await flows_service.create_routing_rule(
            tenant_id=tenant_id, routing_rule_create=rule_create, principal_id="user-123"
        )

        assert result.id == rule_id
        assert result.router_id == router_id
        repository.get_router.assert_called_once_with(router_id)
        repository.create_routing_rule.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_flow_version_succeeds_with_validated_draft(
        self, flows_service, repository, limit_policy_repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status=VersionStatus.DRAFT,
        )
        mock_draft = SimpleNamespace(
            flow_version_id=version_id,
            status="VALIDATED",
        )
        mock_policy = SimpleNamespace(execution_limit_policy_id=uuid4())
        mock_policy_version = SimpleNamespace()
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow_graph_draft = AsyncMock(return_value=mock_draft)
        repository.set_flow_version_status = AsyncMock()
        limit_policy_repository.get_default_policy_for_tenant = AsyncMock(
            return_value=mock_policy
        )
        limit_policy_repository.get_published_policy_version = AsyncMock(
            return_value=mock_policy_version
        )
        validated_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status=VersionStatus.VALIDATED,
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
            min_agent_version_major=None,
            min_agent_version_minor=None,
            min_agent_version_patch=None,
        )
        repository.get_flow_version = AsyncMock(
            side_effect=[mock_version, validated_version]
        )

        result = await flows_service.validate_flow_version(
            tenant_id=tenant_id, flow_id=str(flow_id), flow_version_id=str(version_id)
        )

        assert result.status == VersionStatus.VALIDATED
        repository.get_flow_graph_draft.assert_called_once_with(version_id)
        limit_policy_repository.get_default_policy_for_tenant.assert_called_once_with(
            tenant_id
        )
        repository.set_flow_version_status.assert_called_once_with(
            flow_version_id=version_id, status=VersionStatus.VALIDATED
        )

    @pytest.mark.asyncio
    async def test_validate_flow_version_fails_when_draft_missing(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status=VersionStatus.DRAFT,
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow_graph_draft = AsyncMock(return_value=None)

        with pytest.raises(
            DomainValidationException, match="flow_graph_draft_not_found"
        ):
            await flows_service.validate_flow_version(
                tenant_id=tenant_id,
                flow_id=str(flow_id),
                flow_version_id=str(version_id),
            )

    @pytest.mark.asyncio
    async def test_validate_flow_version_fails_when_draft_not_validated(
        self, flows_service, repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status=VersionStatus.DRAFT,
        )
        mock_draft = SimpleNamespace(
            flow_version_id=version_id,
            status="DRAFT",
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow_graph_draft = AsyncMock(return_value=mock_draft)

        with pytest.raises(
            DomainValidationException, match="flow_graph_draft_not_validated"
        ):
            await flows_service.validate_flow_version(
                tenant_id=tenant_id,
                flow_id=str(flow_id),
                flow_version_id=str(version_id),
            )

    @pytest.mark.asyncio
    async def test_validate_flow_version_fails_when_execution_limit_policy_missing(
        self, flows_service, repository, limit_policy_repository
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            flow_version_id=version_id,
            flow_id=flow_id,
            status=VersionStatus.DRAFT,
        )
        mock_draft = SimpleNamespace(
            flow_version_id=version_id,
            status="VALIDATED",
        )
        repository.get_flow = AsyncMock(return_value=mock_flow)
        repository.get_flow_version = AsyncMock(return_value=mock_version)
        repository.get_flow_graph_draft = AsyncMock(return_value=mock_draft)
        limit_policy_repository.get_default_policy_for_tenant = AsyncMock(
            return_value=None
        )

        with pytest.raises(
            ResourceBlockedServiceException,
            match="execution_limit_policy_not_configured",
        ):
            await flows_service.validate_flow_version(
                tenant_id=tenant_id,
                flow_id=str(flow_id),
                flow_version_id=str(version_id),
            )
