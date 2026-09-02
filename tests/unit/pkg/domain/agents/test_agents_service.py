from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import (
    AgentCreate,
    AgentVersionCreate,
    NodeAgentBindingCreate,
)
from domain.agents.services.agents_service import AgentsService
from exceptions.service_exceptions import NotFoundServiceException


class TestAgentsService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=AgentsRepository)
        repo.get_agent = AsyncMock(return_value=None)
        repo.get_agent_version = AsyncMock(return_value=None)
        repo.db = MagicMock()
        repo.db.get_session = MagicMock()
        return repo

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock()
        events.append_event = AsyncMock()
        return events

    @pytest.fixture
    def agents_service(self, repository, authoring_events):
        return AgentsService(repository=repository, authoring_events=authoring_events)

    @pytest.mark.asyncio
    async def test_list_agents_returns_empty_list_when_no_results(self, agents_service, repository):
        tenant_id = uuid4()
        repository.list_agents = AsyncMock(return_value=[])

        result = await agents_service.list_agents(tenant_id=tenant_id, limit=200)

        assert result == []
        repository.list_agents.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_list_agents_returns_agents_filtered_by_tenant(self, agents_service, repository):
        tenant_id = uuid4()
        agent_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, name="Test Agent")
        repository.list_agents = AsyncMock(return_value=[mock_agent])

        result = await agents_service.list_agents(tenant_id=tenant_id, limit=200)

        assert len(result) == 1
        assert result[0].id == agent_id
        assert result[0].name == "Test Agent"
        repository.list_agents.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_create_agent_creates_agent_with_success(
        self, agents_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        agent_id = uuid4()
        agent_create = AgentCreate(name="New Agent")
        principal_id = "user-123"

        mock_agent = SimpleNamespace(agent_id=agent_id, name="New Agent")
        repository.create_agent = AsyncMock(return_value=mock_agent)

        result = await agents_service.create_agent(
            tenant_id=tenant_id, agent_create=agent_create, principal_id=principal_id
        )

        assert result.id == agent_id
        assert result.name == "New Agent"
        repository.create_agent.assert_called_once_with(
            tenant_id=tenant_id, name="New Agent", created_by=principal_id
        )
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_creates_agent_with_optional_name(
        self, agents_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        agent_id = uuid4()
        agent_create = AgentCreate(name=None)
        principal_id = "user-123"

        mock_agent = SimpleNamespace(agent_id=agent_id, name=None)
        repository.create_agent = AsyncMock(return_value=mock_agent)

        result = await agents_service.create_agent(
            tenant_id=tenant_id, agent_create=agent_create, principal_id=principal_id
        )

        assert result.id == agent_id
        assert result.name is None
        repository.create_agent.assert_called_once_with(
            tenant_id=tenant_id, name=None, created_by=principal_id
        )

    @pytest.mark.asyncio
    async def test_list_agent_versions_returns_empty_list_when_no_results(
        self, agents_service, repository
    ):
        tenant_id = uuid4()
        agent_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id)
        repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.list_agent_versions = AsyncMock(return_value=[])

        result = await agents_service.list_agent_versions(
            tenant_id=tenant_id, agent_id=agent_id, status_filter=None
        )

        assert result == []
        repository.get_agent.assert_called_once_with(agent_id)
        repository.list_agent_versions.assert_called_once_with(
            agent_id=agent_id, status_filter=None
        )

    @pytest.mark.asyncio
    async def test_list_agent_versions_filters_by_status(self, agents_service, repository):
        tenant_id = uuid4()
        agent_id = uuid4()
        version_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            agent_version_id=version_id,
            agent_id=agent_id,
            description="Test version",
            status="PUBLISHED",
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
            supported_tool_schema_version=None,
            supported_tool_config_hash_prefix=None,
            persona_config=None,
            system_prompt=None,
            ai_execution_policy_version_id=None,
        )
        repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.list_agent_versions = AsyncMock(return_value=[mock_version])

        result = await agents_service.list_agent_versions(
            tenant_id=tenant_id, agent_id=agent_id, status_filter=["PUBLISHED"]
        )

        assert len(result) == 1
        assert result[0].id == version_id
        assert result[0].status == "PUBLISHED"
        repository.list_agent_versions.assert_called_once_with(
            agent_id=agent_id, status_filter=["PUBLISHED"]
        )

    @pytest.mark.asyncio
    async def test_create_agent_version_creates_with_provided_version_numbers(
        self, agents_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        agent_id = uuid4()
        version_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id)
        mock_version = SimpleNamespace(
            agent_version_id=version_id,
            agent_id=agent_id,
            description="Test version",
            status="DRAFT",
            version_major=2,
            version_minor=1,
            version_patch=0,
            config_hash=None,
            supported_tool_schema_version=None,
            supported_tool_config_hash_prefix=None,
            persona_config=None,
            system_prompt=None,
            ai_execution_policy_version_id=None,
        )
        repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.create_agent_version = AsyncMock(return_value=mock_version)
        agent_version_create = AgentVersionCreate(
            version_major=2, version_minor=1, version_patch=0, description="Test version"
        )

        result = await agents_service.create_agent_version(
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_version_create=agent_version_create,
            principal_id="user-123",
        )

        assert result.id == version_id
        assert result.version_major == 2
        assert result.version_minor == 1
        assert result.version_patch == 0
        repository.create_agent_version.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_node_agent_binding_creates_with_success(
        self, agents_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        flow_id = uuid4()
        version_id = uuid4()
        node_id = uuid4()
        agent_id = uuid4()
        agent_version_id = uuid4()
        binding_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id)
        mock_agent_version = SimpleNamespace(agent_version_id=agent_version_id, agent_id=agent_id)
        mock_flow = SimpleNamespace(flow_id=flow_id, tenant_id=tenant_id)
        mock_flow_version = SimpleNamespace(flow_version_id=version_id, flow_id=flow_id)
        mock_node = SimpleNamespace(node_id=node_id, flow_version_id=version_id)
        mock_binding = SimpleNamespace(
            node_agent_binding_id=binding_id,
            node_id=node_id,
            agent_version_id=agent_version_id,
        )
        repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.get_agent_version = AsyncMock(return_value=mock_agent_version)
        repository.create_node_agent_binding = AsyncMock(return_value=mock_binding)
        binding_create = NodeAgentBindingCreate(node_id=node_id, agent_version_id=agent_version_id)

        async def mock_get_session():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, stmt):
                    class MockResult:
                        def scalar_one_or_none(self):
                            if "node" in str(stmt).lower():
                                return mock_node
                            elif "flow_version" in str(stmt).lower():
                                return mock_flow_version
                            elif "flow" in str(stmt).lower():
                                return mock_flow
                            return None

                    return MockResult()

            return MockSession()

        repository.db.get_session = mock_get_session

        result = await agents_service.create_node_agent_binding(
            tenant_id=tenant_id,
            node_agent_binding_create=binding_create,
            principal_id="user-123",
        )

        assert result.id == binding_id
        assert result.node_id == node_id
        assert result.agent_version_id == agent_version_id
        repository.create_node_agent_binding.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_node_agent_binding_raises_when_tenant_mismatch(
        self, agents_service, repository
    ):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        node_id = uuid4()
        agent_version_id = uuid4()
        agent_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=other_tenant_id)
        mock_agent_version = SimpleNamespace(agent_version_id=agent_version_id, agent_id=agent_id)
        mock_flow = SimpleNamespace(flow_id=uuid4(), tenant_id=tenant_id)
        mock_flow_version = SimpleNamespace(flow_version_id=uuid4(), flow_id=uuid4())
        mock_node = SimpleNamespace(node_id=node_id, flow_version_id=uuid4())
        repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.get_agent_version = AsyncMock(return_value=mock_agent_version)
        binding_create = NodeAgentBindingCreate(node_id=node_id, agent_version_id=agent_version_id)

        async def mock_get_session():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, stmt):
                    class MockResult:
                        def scalar_one_or_none(self):
                            if "node" in str(stmt).lower():
                                return mock_node
                            elif "flow_version" in str(stmt).lower():
                                return mock_flow_version
                            elif "flow" in str(stmt).lower():
                                return mock_flow
                            return None

                    return MockResult()

            return MockSession()

        repository.db.get_session = mock_get_session

        with pytest.raises(NotFoundServiceException, match="agent_not_found"):
            await agents_service.create_node_agent_binding(
                tenant_id=tenant_id,
                node_agent_binding_create=binding_create,
                principal_id="user-123",
            )
