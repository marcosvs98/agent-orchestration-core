from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.flows.controllers.flows_controller import FlowsController
from domain.flows.schemas.flows import Flow, FlowCreate
from domain.flows.services.flows_service import FlowsService
from exceptions.service_exceptions import DomainValidationException
from utils.auth import AuthContext


class TestFlowsController:
    @pytest.fixture
    def service(self):
        svc = MagicMock(spec=FlowsService)
        svc.create_flow = AsyncMock()
        svc.get_flow = AsyncMock()
        svc.list_flows = AsyncMock()
        return svc

    @pytest.fixture
    def controller(self, service):
        return FlowsController(service=service)

    @pytest.mark.asyncio
    async def test_create_flow_returns_flow_when_name_valid(self, controller, service):
        tenant_id = uuid4()
        flow_id = uuid4()
        flow_create = FlowCreate(name="New Flow")
        principal_id = "user-123"

        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id=principal_id,
            scopes={"flows:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        expected_response = Flow(
            id=flow_id, name="New Flow", description=None, tags=None, created_by=principal_id
        )
        service.create_flow = AsyncMock(return_value=expected_response)

        result = await controller.create_flow(flow_create=flow_create, auth=auth)

        assert result.id == flow_id
        assert result.name == "New Flow"
        assert result.description is None
        assert result.tags is None
        assert result.created_by == principal_id
        service.create_flow.assert_called_once_with(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )

    @pytest.mark.asyncio
    async def test_create_flow_with_description_and_tags(self, controller, service):
        tenant_id = uuid4()
        flow_id = uuid4()
        flow_create = FlowCreate(
            name="New Flow", description="Flow description", tags=["tag1", "tag2"]
        )
        principal_id = "user-123"

        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id=principal_id,
            scopes={"flows:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        expected_response = Flow(
            id=flow_id,
            name="New Flow",
            description="Flow description",
            tags=["tag1", "tag2"],
            created_by=principal_id,
        )
        service.create_flow = AsyncMock(return_value=expected_response)

        result = await controller.create_flow(flow_create=flow_create, auth=auth)

        assert result.id == flow_id
        assert result.name == "New Flow"
        assert result.description == "Flow description"
        assert result.tags == ["tag1", "tag2"]
        assert result.created_by == principal_id
        service.create_flow.assert_called_once_with(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )

    @pytest.mark.asyncio
    async def test_create_flow_raises_when_name_empty(self, controller, service):
        tenant_id = uuid4()
        flow_create = FlowCreate(name="")
        principal_id = "user-123"

        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id=principal_id,
            scopes={"flows:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        service.create_flow = AsyncMock(
            side_effect=DomainValidationException(message="flow_name_required")
        )

        with pytest.raises(DomainValidationException, match="flow_name_required"):
            await controller.create_flow(flow_create=flow_create, auth=auth)

        service.create_flow.assert_called_once_with(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )

    @pytest.mark.asyncio
    async def test_create_flow_raises_when_name_only_whitespace(self, controller, service):
        tenant_id = uuid4()
        flow_create = FlowCreate(name="   ")
        principal_id = "user-123"

        auth = AuthContext(
            tenant_id=tenant_id,
            principal_type="human",
            principal_id=principal_id,
            scopes={"flows:create"},
            token_issuer="test-issuer",
            token_audience="test-audience",
            expires_at=9999999999,
        )

        service.create_flow = AsyncMock(
            side_effect=DomainValidationException(message="flow_name_required")
        )

        with pytest.raises(DomainValidationException, match="flow_name_required"):
            await controller.create_flow(flow_create=flow_create, auth=auth)

        service.create_flow.assert_called_once_with(
            tenant_id=tenant_id, flow_create=flow_create, principal_id=principal_id
        )
