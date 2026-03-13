from uuid import UUID


from domain.agents.repositories.agents_repository import AgentsRepository
from domain.common.schemas.versioning import VersionStatus
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from domain.tools.ports.service import ToolsServicePort
from domain.tools.repositories.tools_repository import ToolsRepository
from domain.tools.schemas.tools import (
    AgentVersionToolBinding,
    AgentVersionToolBindingCreate,
    Tool,
    AvailableTool,
    ToolConfig,
    ToolConfigCreate,
    ToolImportRequest,
)
from domain.tools.schemas.tool_config_types import ToolConfigConfig
from domain.tools.services.openapi_parser import OpenAPIParser
from domain.governance.schemas.authoring_events import AuthoringEventType, ChangeType
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)


class ToolsService(ToolsServicePort):
    def __init__(
        self,
        repository: ToolsRepository,
        agents_repository: AgentsRepository,
        authoring_events: AuthoringEventRepository,
        tracer: RuntimeTracerPort,
    ) -> None:
        self.repository = repository
        self.agents_repository = agents_repository
        self.authoring_events = authoring_events
        self.tracer = tracer
        self.openapi_parser = OpenAPIParser()

    async def import_tool(
        self,
        *,
        tenant_id: UUID,
        tool_import_request: ToolImportRequest,
        principal_id: str,
    ) -> Tool:
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.parse_openapi_spec",
            input={"openapi_url": tool_import_request.openapi_url},
        ):
            parsed_spec = await self.openapi_parser.parse_openapi_spec(
                tool_import_request.openapi_url
            )
        tool_name = tool_import_request.name or parsed_spec.get("title")
        if not tool_name:
            raise DomainValidationException(
                message="tool_name_required_from_openapi_or_request"
            )
        existing_tool = await self.repository.get_tool_by_name(tool_name)
        if existing_tool is not None:
            tool_model = existing_tool
        else:
            tool_model = await self.repository.create_tool(
                name=tool_name, created_by=principal_id
            )

        operations = self.openapi_parser.extract_operations(parsed_spec)
        base_url = (
            parsed_spec.get("servers", [{}])[0].get("url", "")
            if parsed_spec.get("servers")
            else ""
        )

        patch_start = await self.repository.get_max_version_patch(
            tool_id=tool_model.tool_id,
            tenant_id=tenant_id,
            version_major=1,
            version_minor=0,
        )
        patch_start += 1

        for i, op in enumerate(operations):
            full_url = f"{base_url}{op['path']}" if base_url else op["path"]

            tool_config_dict = ToolConfigConfig(
                url=full_url,
                method=op["method"],
                request_schema=op["request_schema"],
                response_schema=op["response_schema"],
                operation_id=op["operation_id"],
            )

            await self.repository.create_tool_config(
                tool_id=tool_model.tool_id,
                tenant_id=tenant_id,
                config=tool_config_dict,
                version_major=1,
                version_minor=0,
                version_patch=patch_start + i,
                schema_version=1,
                created_by=principal_id,
            )

        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.append_event_import",
            input={"tenant_id": str(tenant_id), "resource_id": str(tool_model.tool_id)},
        ):
            await self.authoring_events.append_event(
                tenant_id=tenant_id,
                resource_type="tool",
                resource_id=tool_model.tool_id,
                version_id=None,
                event_type=AuthoringEventType.TOOL_IMPORTED.value,
                change_type=ChangeType.CREATE.value,
                principal_id=principal_id,
                justification="import tool from openapi",
                schema_version=1,
            )
        return Tool(id=tool_model.tool_id, name=tool_model.name)

    async def list_tools(self, *, tenant_id: UUID, limit: int = 200) -> list[Tool]:
        tools = await self.repository.list_tools(tenant_id=tenant_id, limit=limit)
        return [Tool(id=tool.tool_id, name=tool.name) for tool in tools]

    async def list_tool_configs(
        self,
        *,
        tenant_id: UUID,
        status_filter: list[str] | None = None,
        limit: int = 200,
    ) -> list[ToolConfig]:
        configs = await self.repository.list_tool_configs(
            tenant_id=tenant_id, status_filter=status_filter, limit=limit
        )
        return [
            ToolConfig(
                id=config.tool_config_id,
                tool_id=config.tool_id,
                config=config.config,
                status=config.status,
                version_major=config.version_major,
                version_minor=config.version_minor,
                version_patch=config.version_patch,
                config_hash=config.config_hash,
                schema_version=config.schema_version,
            )
            for config in configs
        ]

    async def list_available_tools_for_execution(
        self, *, tenant_id: UUID, limit: int = 200
    ) -> list[AvailableTool]:
        tool_configs = await self.list_tool_configs(
            tenant_id=tenant_id,
            status_filter=[VersionStatus.PUBLISHED.value],
            limit=limit,
        )
        if not tool_configs:
            return []

        tools = await self.repository.list_tools(
            tenant_id=tenant_id,
            status_filter=[VersionStatus.PUBLISHED.value],
            limit=limit,
        )
        tool_map = {tool.tool_id: tool for tool in tools}
        available_tools = []
        for config in tool_configs:
            tool = tool_map.get(config.tool_id)
            if tool:
                available_tools.append(
                    AvailableTool.model_validate(
                        {
                            "name": tool.name,
                            "tool_id": config.tool_id,
                            "tool_config_id": config.id,
                        }
                    )
                )

        return available_tools

    async def create_tool_config(
        self,
        *,
        tenant_id: UUID,
        tool_config_create: ToolConfigCreate,
        principal_id: str,
    ) -> ToolConfig:
        tool = await self.repository.get_tool(tool_config_create.tool_id)
        if tool is None:
            raise NotFoundServiceException(message="tool_not_found")
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.create_tool_config",
            input={
                "tool_id": str(tool_config_create.tool_id),
                "tenant_id": str(tenant_id),
            },
        ):
            model = await self.repository.create_tool_config(
                tool_id=tool_config_create.tool_id,
                tenant_id=tenant_id,
                source_config_id=tool_config_create.source_config_id,
                version_major=tool_config_create.version_major,
                version_minor=tool_config_create.version_minor,
                version_patch=tool_config_create.version_patch,
                config=tool_config_create.config or {},
                schema_version=tool_config_create.schema_version,
                created_by=principal_id,
            )
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.append_event_tool_config",
            input={
                "tenant_id": str(tenant_id),
                "resource_id": str(model.tool_config_id),
            },
        ):
            await self.authoring_events.append_event(
                tenant_id=tenant_id,
                resource_type="tool_config",
                resource_id=model.tool_config_id,
                version_id=None,
                event_type=AuthoringEventType.TOOL_CONFIG_CREATED.value,
                change_type=ChangeType.CREATE.value,
                principal_id=principal_id,
                justification="create tool config",
                schema_version=1,
            )
        return ToolConfig(
            id=model.tool_config_id,
            tool_id=model.tool_id,
            config=model.config,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            schema_version=model.schema_version,
        )

    async def create_agent_version_tool_binding(
        self,
        *,
        tenant_id: UUID,
        binding_create: AgentVersionToolBindingCreate,
        principal_id: str,
    ) -> AgentVersionToolBinding:
        agent_version = await self.agents_repository.get_agent_version(
            binding_create.agent_version_id
        )
        if agent_version is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        agent = await self.agents_repository.get_agent(agent_version.agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")

        tool_config = await self.repository.get_tool_config(
            binding_create.tool_config_id
        )
        if tool_config is None or tool_config.tenant_id != tenant_id:
            raise NotFoundServiceException(message="tool_config_not_found")
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.create_agent_version_tool_binding",
            input={
                "agent_version_id": str(binding_create.agent_version_id),
                "tool_config_id": str(binding_create.tool_config_id),
            },
        ):
            model = await self.repository.create_agent_version_tool_binding(
                agent_version_id=binding_create.agent_version_id,
                tool_config_id=binding_create.tool_config_id,
                created_by=principal_id,
            )
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.append_event_binding",
            input={
                "tenant_id": str(tenant_id),
                "resource_id": str(model.agent_version_tool_binding_id),
            },
        ):
            await self.authoring_events.append_event(
                tenant_id=tenant_id,
                resource_type="agent_version_tool_binding",
                resource_id=model.agent_version_tool_binding_id,
                version_id=None,
                event_type=AuthoringEventType.AGENT_VERSION_TOOL_BINDING_CREATED.value,
                change_type=ChangeType.CREATE.value,
                principal_id=principal_id,
                justification="create agent version tool binding",
                schema_version=1,
            )
        return AgentVersionToolBinding(
            id=model.agent_version_tool_binding_id,
            agent_version_id=model.agent_version_id,
            tool_config_id=model.tool_config_id,
        )
