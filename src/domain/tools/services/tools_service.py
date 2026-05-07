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
    AvailableTool,
    Tool,
    ToolConfig,
    ToolConfigCreate,
    ToolImportRequest,
    ToolImportResult,
)
from domain.tools.schemas.tool_config_types import ToolConfigConfig
from domain.tools.services.openapi_parser import OpenAPIParser
from domain.tools.services.tool_catalog_indexer import ToolCatalogIndexer
from domain.tools.services.tool_import_http_base import (
    DEFAULT_UORA_IMPORT_TOOL_HEADERS,
    resolve_tool_import_base_url,
)
from domain.governance.schemas.authoring_events import AuthoringEventType, ChangeType
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class ToolsService(ToolsServicePort):
    def __init__(
        self,
        repository: ToolsRepository,
        agents_repository: AgentsRepository,
        authoring_events: AuthoringEventRepository,
        tracer: RuntimeTracerPort,
        tool_catalog_indexer: ToolCatalogIndexer | None = None,
    ) -> None:
        self.repository = repository
        self.agents_repository = agents_repository
        self.authoring_events = authoring_events
        self.tracer = tracer
        self.openapi_parser = OpenAPIParser()
        self.tool_catalog_indexer = tool_catalog_indexer

    async def import_tool(
        self,
        *,
        tenant_id: UUID,
        tool_import_request: ToolImportRequest,
        principal_id: str,
    ) -> ToolImportResult:
        with self.tracer.observe(
            as_type="tool",
            name="domain.tools.tools_service.parse_openapi_spec",
            input={"openapi_url": tool_import_request.openapi_url},
        ):
            parsed_spec = await self.openapi_parser.parse_openapi_spec(
                tool_import_request.openapi_url
            )
        operations = self.openapi_parser.extract_operations(parsed_spec)
        if not operations:
            raise DomainValidationException(message="openapi_spec_without_operations")
        base_url = resolve_tool_import_base_url(
            openapi_servers=parsed_spec.get("servers"),
            openapi_fetch_url=tool_import_request.openapi_url,
        )
        imported_tools: list[Tool] = []
        for op in operations:
            operation_id = op["operation_id"]
            existing_tool = await self.repository.get_tool_by_name(operation_id)
            if existing_tool is not None:
                tool_model = existing_tool
            else:
                tool_model = await self.repository.create_tool(
                    name=operation_id, created_by=principal_id
                )
            patch_start = await self.repository.get_max_version_patch(
                tool_id=tool_model.tool_id,
                tenant_id=tenant_id,
                version_major=1,
                version_minor=0,
            )
            path = str(op["path"])
            path_norm = path if path.startswith("/") else (f"/{path}" if path else "")
            full_url = f"{base_url}{path_norm}" if base_url else path

            tool_config_dict = ToolConfigConfig(
                base_url=base_url or None,
                url=full_url,
                path=op["path"],
                method=op["method"],
                request_schema=op["request_schema"],
                response_schema=op["response_schema"],
                operation_id=op["operation_id"],
                summary=op.get("summary"),
                description=op.get("description"),
                examples=op.get("examples"),
                headers=dict(DEFAULT_UORA_IMPORT_TOOL_HEADERS),
            )

            created_tool_config = await self.repository.create_tool_config(
                tool_id=tool_model.tool_id,
                tenant_id=tenant_id,
                config=tool_config_dict,
                version_major=1,
                version_minor=0,
                version_patch=patch_start + 1,
                schema_version=1,
                created_by=principal_id,
            )
            await self._index_tool_catalog_document(
                tenant_id=tenant_id,
                tool_id=tool_model.tool_id,
                tool_name=tool_model.name,
                tool_config_id=created_tool_config.tool_config_id,
                config=created_tool_config.config,
                version=f"{created_tool_config.version_major}.{created_tool_config.version_minor}.{created_tool_config.version_patch}",
            )
            with self.tracer.observe(
                as_type="tool",
                name="domain.tools.tools_service.append_event_import",
                input={
                    "tenant_id": str(tenant_id),
                    "resource_id": str(tool_model.tool_id),
                },
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
            await self.publish_tool_config(
                tenant_id=tenant_id,
                tool_config_id=created_tool_config.tool_config_id,
                principal_id=principal_id,
            )
            imported_tools.append(Tool(id=tool_model.tool_id, name=tool_model.name))
        return ToolImportResult(
            imported_count=len(imported_tools),
            tools=imported_tools,
        )

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
                config_data = config.config or {}
                available_tools.append(
                    AvailableTool.model_validate(
                        {
                            "name": tool.name,
                            "tool_id": config.tool_id,
                            "tool_config_id": config.id,
                            "summary": config_data.get("summary"),
                            "description": config_data.get("description"),
                            "operation_id": config_data.get("operation_id"),
                            "method": config_data.get("method"),
                            "path": config_data.get("path"),
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
                config=(
                    tool_config_create.config.model_dump(mode="json", exclude_none=True)
                    if tool_config_create.config is not None
                    else {}
                ),
                schema_version=tool_config_create.schema_version,
                created_by=principal_id,
            )
        await self._index_tool_catalog_document(
            tenant_id=tenant_id,
            tool_id=model.tool_id,
            tool_name=tool.name,
            tool_config_id=model.tool_config_id,
            config=model.config,
            version=f"{model.version_major}.{model.version_minor}.{model.version_patch}",
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

        tool_config = await self.repository.get_tool_config(binding_create.tool_config_id)
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

    async def list_tool_bindings_by_agent_version(
        self, *, tenant_id: UUID, agent_version_id: UUID
    ) -> list[AgentVersionToolBinding]:
        models = await self.repository.list_tool_bindings_by_agent_version_id(
            tenant_id=tenant_id, agent_version_id=agent_version_id
        )
        return [
            AgentVersionToolBinding(
                id=m.agent_version_tool_binding_id,
                agent_version_id=m.agent_version_id,
                tool_config_id=m.tool_config_id,
            )
            for m in models
        ]

    def _tool_config_to_schema(self, src: object) -> ToolConfig:
        return ToolConfig(
            id=src.tool_config_id,
            tool_id=src.tool_id,
            config=src.config,
            status=src.status,
            version_major=src.version_major,
            version_minor=src.version_minor,
            version_patch=src.version_patch,
            config_hash=src.config_hash,
            schema_version=src.schema_version,
        )

    async def publish_tool_config(
        self,
        *,
        tenant_id: UUID,
        tool_config_id: UUID,
        principal_id: str,
    ) -> ToolConfig:
        model = await self.repository.get_tool_config(tool_config_id)
        if model is None or model.tenant_id != tenant_id:
            raise NotFoundServiceException(message="tool_config_not_found")
        current = str(model.status)
        if current == VersionStatus.PUBLISHED.value:
            return self._tool_config_to_schema(model)
        if current not in (
            VersionStatus.DRAFT.value,
            VersionStatus.VALIDATED.value,
        ):
            raise ResourceBlockedServiceException(message="tool_config_not_publishable")
        await self.repository.set_tool_config_status(
            tool_config_id=tool_config_id, status=VersionStatus.PUBLISHED
        )
        tool = await self.repository.get_tool(model.tool_id)
        refreshed = await self.repository.get_tool_config(tool_config_id)
        if refreshed is None:
            raise NotFoundServiceException(message="tool_config_not_found")
        await self._index_tool_catalog_document(
            tenant_id=tenant_id,
            tool_id=refreshed.tool_id,
            tool_name=tool.name if tool else None,
            tool_config_id=refreshed.tool_config_id,
            config=refreshed.config,
            version=f"{refreshed.version_major}.{refreshed.version_minor}.{refreshed.version_patch}",
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="tool_config",
            resource_id=tool_config_id,
            version_id=None,
            event_type=AuthoringEventType.TOOL_CONFIG_PUBLISHED.value,
            change_type=ChangeType.UPDATE.value,
            principal_id=principal_id,
            justification="publish tool config",
            schema_version=1,
        )
        return self._tool_config_to_schema(refreshed)

    async def deprecate_tool_config(
        self,
        *,
        tenant_id: UUID,
        tool_config_id: UUID,
        principal_id: str,
    ) -> ToolConfig:
        model = await self.repository.get_tool_config(tool_config_id)
        if model is None or model.tenant_id != tenant_id:
            raise NotFoundServiceException(message="tool_config_not_found")
        current = str(model.status)
        if current == VersionStatus.DEPRECATED.value:
            return self._tool_config_to_schema(model)
        if current in (VersionStatus.DISABLED.value,):
            raise ResourceBlockedServiceException(message="tool_config_not_deprecatable")
        await self.repository.set_tool_config_status(
            tool_config_id=tool_config_id, status=VersionStatus.DEPRECATED
        )
        refreshed = await self.repository.get_tool_config(tool_config_id)
        if refreshed is None:
            raise NotFoundServiceException(message="tool_config_not_found")
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="tool_config",
            resource_id=tool_config_id,
            version_id=None,
            event_type=AuthoringEventType.TOOL_CONFIG_DEPRECATED.value,
            change_type=ChangeType.UPDATE.value,
            principal_id=principal_id,
            justification="deprecate tool config",
            schema_version=1,
        )
        return self._tool_config_to_schema(refreshed)

    async def disable_tool_config(
        self,
        *,
        tenant_id: UUID,
        tool_config_id: UUID,
        principal_id: str,
    ) -> ToolConfig:
        model = await self.repository.get_tool_config(tool_config_id)
        if model is None or model.tenant_id != tenant_id:
            raise NotFoundServiceException(message="tool_config_not_found")
        current = str(model.status)
        if current == VersionStatus.DISABLED.value:
            return self._tool_config_to_schema(model)
        if current not in (
            VersionStatus.PUBLISHED.value,
            VersionStatus.DEPRECATED.value,
        ):
            raise ResourceBlockedServiceException(message="tool_config_not_disableable")
        await self.repository.set_tool_config_status(
            tool_config_id=tool_config_id, status=VersionStatus.DISABLED
        )
        refreshed = await self.repository.get_tool_config(tool_config_id)
        if refreshed is None:
            raise NotFoundServiceException(message="tool_config_not_found")
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="tool_config",
            resource_id=tool_config_id,
            version_id=None,
            event_type=AuthoringEventType.TOOL_CONFIG_DISABLED.value,
            change_type=ChangeType.UPDATE.value,
            principal_id=principal_id,
            justification="disable tool config",
            schema_version=1,
        )
        return self._tool_config_to_schema(refreshed)

    async def _index_tool_catalog_document(
        self,
        *,
        tenant_id: UUID,
        tool_id: UUID,
        tool_name: str | None,
        tool_config_id: UUID,
        config: dict[str, object] | None,
        version: str,
    ) -> None:
        if self.tool_catalog_indexer is None:
            return
        document = self.tool_catalog_indexer.build_document(
            tool_id=tool_id,
            tool_config_id=tool_config_id,
            tool_name=tool_name,
            config=config,
            version=version,
        )
        await self.tool_catalog_indexer.index_document(
            tenant_id=tenant_id,
            document=document,
        )
