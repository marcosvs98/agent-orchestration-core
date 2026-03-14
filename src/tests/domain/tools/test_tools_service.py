from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.agents.repositories.agents_repository import AgentsRepository
from domain.tools.repositories.tools_repository import ToolsRepository
from domain.tools.schemas.tools import (
    AgentVersionToolBindingCreate,
    ToolConfigCreate,
    ToolImportRequest,
)
from domain.tools.services.tools_service import ToolsService
from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)


class TestToolsService:
    @pytest.fixture
    def repository(self):
        repo = MagicMock(spec=ToolsRepository)
        repo.get_tool = AsyncMock(return_value=None)
        repo.get_tool_by_name = AsyncMock(return_value=None)
        repo.get_tool_config = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def agents_repository(self):
        repo = MagicMock(spec=AgentsRepository)
        repo.get_agent = AsyncMock(return_value=None)
        repo.get_agent_version = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def authoring_events(self):
        events = MagicMock()
        events.append_event = AsyncMock()
        return events

    @pytest.fixture
    def tools_service(self, repository, agents_repository, authoring_events):
        indexer = MagicMock(spec=ToolCatalogIndexer)
        indexer.build_document = MagicMock()
        indexer.index_document = AsyncMock(return_value=True)
        return ToolsService(
            repository=repository,
            agents_repository=agents_repository,
            authoring_events=authoring_events,
            tracer=MagicMock(),
            tool_catalog_indexer=indexer,
        )

    @pytest.mark.asyncio
    async def test_import_tool_creates_new_tool_when_not_exists(
        self, tools_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        tool_id = uuid4()
        tool_import_request = ToolImportRequest(
            openapi_url="https://api.example.com/openapi.json", name="Test Tool"
        )
        principal_id = "user-123"

        mock_tool = SimpleNamespace(tool_id=tool_id, name="Test Tool")
        repository.get_tool_by_name = AsyncMock(return_value=None)
        repository.create_tool = AsyncMock(return_value=mock_tool)
        created_tool_config = SimpleNamespace(
            tool_config_id=uuid4(),
            tool_id=tool_id,
            config={},
            version_major=1,
            version_minor=0,
            version_patch=0,
        )
        repository.create_tool_config = AsyncMock(return_value=created_tool_config)
        tools_service.openapi_parser.parse_openapi_spec = AsyncMock(
            return_value={
                "title": "Test Tool",
                "version": "1.0.0",
                "paths": {
                    "/health": {
                        "get": {
                            "operationId": "health_check",
                            "summary": "Health check",
                            "description": "Health check endpoint",
                            "responses": {"200": {"content": {}}},
                        }
                    }
                },
            }
        )

        result = await tools_service.import_tool(
            tenant_id=tenant_id,
            tool_import_request=tool_import_request,
            principal_id=principal_id,
        )

        assert result.id == tool_id
        assert result.name == "Test Tool"
        repository.create_tool.assert_called_once_with(
            name="Test Tool", created_by=principal_id
        )
        tools_service.tool_catalog_indexer.index_document.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_tool_reuses_existing_tool_when_name_exists(
        self, tools_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        tool_id = uuid4()
        tool_import_request = ToolImportRequest(
            openapi_url="https://api.example.com/openapi.json", name="Existing Tool"
        )
        principal_id = "user-123"

        mock_tool = SimpleNamespace(tool_id=tool_id, name="Existing Tool")
        repository.get_tool_by_name = AsyncMock(return_value=mock_tool)
        created_tool_config = SimpleNamespace(
            tool_config_id=uuid4(),
            tool_id=tool_id,
            config={},
            version_major=1,
            version_minor=0,
            version_patch=0,
        )
        repository.create_tool_config = AsyncMock(return_value=created_tool_config)
        tools_service.openapi_parser.parse_openapi_spec = AsyncMock(
            return_value={
                "title": "Existing Tool",
                "version": "1.0.0",
                "paths": {
                    "/health": {
                        "get": {
                            "operationId": "health_check",
                            "summary": "Health check",
                            "description": "Health check endpoint",
                            "responses": {"200": {"content": {}}},
                        }
                    }
                },
            }
        )

        result = await tools_service.import_tool(
            tenant_id=tenant_id,
            tool_import_request=tool_import_request,
            principal_id=principal_id,
        )

        assert result.id == tool_id
        assert result.name == "Existing Tool"
        repository.create_tool.assert_not_called()
        tools_service.tool_catalog_indexer.index_document.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tools_returns_empty_list_when_no_results(
        self, tools_service, repository
    ):
        tenant_id = uuid4()
        repository.list_tools = AsyncMock(return_value=[])

        result = await tools_service.list_tools(tenant_id=tenant_id, limit=200)

        assert result == []
        repository.list_tools.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools_filtered_by_tenant(
        self, tools_service, repository
    ):
        tenant_id = uuid4()
        tool_id = uuid4()
        mock_tool = SimpleNamespace(tool_id=tool_id, name="Test Tool")
        repository.list_tools = AsyncMock(return_value=[mock_tool])

        result = await tools_service.list_tools(tenant_id=tenant_id, limit=200)

        assert len(result) == 1
        assert result[0].id == tool_id
        assert result[0].name == "Test Tool"
        repository.list_tools.assert_called_once_with(tenant_id=tenant_id, limit=200)

    @pytest.mark.asyncio
    async def test_list_tool_configs_returns_empty_list_when_no_results(
        self, tools_service, repository
    ):
        tenant_id = uuid4()
        repository.list_tool_configs = AsyncMock(return_value=[])

        result = await tools_service.list_tool_configs(
            tenant_id=tenant_id, status_filter=None, limit=200
        )

        assert result == []
        repository.list_tool_configs.assert_called_once_with(
            tenant_id=tenant_id, status_filter=None, limit=200
        )

    @pytest.mark.asyncio
    async def test_list_tool_configs_filters_by_status(
        self, tools_service, repository
    ):
        tenant_id = uuid4()
        config_id = uuid4()
        tool_id = uuid4()
        mock_config = SimpleNamespace(
            tool_config_id=config_id,
            tool_id=tool_id,
            config={"url": "https://api.example.com"},
            status="PUBLISHED",
            version_major=1,
            version_minor=0,
            version_patch=0,
            config_hash=None,
            schema_version=None,
        )
        repository.list_tool_configs = AsyncMock(return_value=[mock_config])

        result = await tools_service.list_tool_configs(
            tenant_id=tenant_id, status_filter=["PUBLISHED"], limit=200
        )

        assert len(result) == 1
        assert result[0].id == config_id
        assert result[0].status == "PUBLISHED"
        repository.list_tool_configs.assert_called_once_with(
            tenant_id=tenant_id, status_filter=["PUBLISHED"], limit=200
        )

    @pytest.mark.asyncio
    async def test_create_tool_config_creates_with_provided_version_numbers(
        self, tools_service, repository, authoring_events
    ):
        tenant_id = uuid4()
        tool_id = uuid4()
        config_id = uuid4()
        mock_tool = SimpleNamespace(tool_id=tool_id, name="Test Tool")
        mock_config = SimpleNamespace(
            tool_config_id=config_id,
            tool_id=tool_id,
            config={"url": "https://api.example.com"},
            status="DRAFT",
            version_major=2,
            version_minor=1,
            version_patch=0,
            config_hash=None,
            schema_version=1,
        )
        repository.get_tool = AsyncMock(return_value=mock_tool)
        repository.create_tool_config = AsyncMock(return_value=mock_config)
        tool_config_create = ToolConfigCreate(
            tool_id=tool_id,
            version_major=2,
            version_minor=1,
            version_patch=0,
            config={"url": "https://api.example.com"},
            schema_version=1,
        )

        result = await tools_service.create_tool_config(
            tenant_id=tenant_id,
            tool_config_create=tool_config_create,
            principal_id="user-123",
        )

        assert result.id == config_id
        assert result.version_major == 2
        assert result.version_minor == 1
        assert result.version_patch == 0
        repository.create_tool_config.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_version_tool_binding_creates_with_success(
        self, tools_service, repository, agents_repository, authoring_events
    ):
        tenant_id = uuid4()
        agent_id = uuid4()
        agent_version_id = uuid4()
        tool_config_id = uuid4()
        binding_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id)
        mock_agent_version = SimpleNamespace(
            agent_version_id=agent_version_id, agent_id=agent_id
        )
        mock_tool_config = SimpleNamespace(
            tool_config_id=tool_config_id, tenant_id=tenant_id
        )
        mock_binding = SimpleNamespace(
            agent_version_tool_binding_id=binding_id,
            agent_version_id=agent_version_id,
            tool_config_id=tool_config_id,
        )
        agents_repository.get_agent_version = AsyncMock(
            return_value=mock_agent_version
        )
        agents_repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.get_tool_config = AsyncMock(return_value=mock_tool_config)
        repository.create_agent_version_tool_binding = AsyncMock(
            return_value=mock_binding
        )
        binding_create = AgentVersionToolBindingCreate(
            agent_version_id=agent_version_id, tool_config_id=tool_config_id
        )

        result = await tools_service.create_agent_version_tool_binding(
            tenant_id=tenant_id, binding_create=binding_create, principal_id="user-123"
        )

        assert result.id == binding_id
        assert result.agent_version_id == agent_version_id
        assert result.tool_config_id == tool_config_id
        repository.create_agent_version_tool_binding.assert_called_once()
        authoring_events.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_version_tool_binding_raises_when_tenant_mismatch(
        self, tools_service, repository, agents_repository
    ):
        tenant_id = uuid4()
        other_tenant_id = uuid4()
        agent_id = uuid4()
        agent_version_id = uuid4()
        tool_config_id = uuid4()
        mock_agent = SimpleNamespace(agent_id=agent_id, tenant_id=tenant_id)
        mock_agent_version = SimpleNamespace(
            agent_version_id=agent_version_id, agent_id=agent_id
        )
        mock_tool_config = SimpleNamespace(
            tool_config_id=tool_config_id, tenant_id=other_tenant_id
        )
        agents_repository.get_agent_version = AsyncMock(
            return_value=mock_agent_version
        )
        agents_repository.get_agent = AsyncMock(return_value=mock_agent)
        repository.get_tool_config = AsyncMock(return_value=mock_tool_config)
        binding_create = AgentVersionToolBindingCreate(
            agent_version_id=agent_version_id, tool_config_id=tool_config_id
        )

        with pytest.raises(NotFoundServiceException, match="tool_config_not_found"):
            await tools_service.create_agent_version_tool_binding(
                tenant_id=tenant_id,
                binding_create=binding_create,
                principal_id="user-123",
            )
