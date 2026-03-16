from uuid import UUID

from domain.agents.ports.service import AgentsServicePort
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.agents.schemas.agents import (
    Agent,
    AgentCreate,
    AgentVersion,
    AgentVersionCreate,
    NodeAgentBinding,
    NodeAgentBindingCreate,
    PersonaConfig,
)
from domain.governance.schemas.authoring_events import AuthoringEventType, ChangeType
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.governance.repositories.authoring_event_repository import (
    AuthoringEventRepository,
)
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class AgentsService(AgentsServicePort):
    def __init__(
        self, repository: AgentsRepository, authoring_events: AuthoringEventRepository
    ) -> None:
        self.repository = repository
        self.authoring_events = authoring_events

    async def list_agents(self, *, tenant_id: UUID, limit: int = 200) -> list[Agent]:
        agents = await self.repository.list_agents(tenant_id=tenant_id, limit=limit)
        return [Agent(id=agent.agent_id, name=agent.name) for agent in agents]

    async def create_agent(
        self, *, tenant_id: UUID, agent_create: AgentCreate, principal_id: str
    ) -> Agent:
        model = await self.repository.create_agent(
            tenant_id=tenant_id, name=agent_create.name, created_by=principal_id
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="agent",
            resource_id=model.agent_id,
            version_id=None,
            event_type=AuthoringEventType.AGENT_CREATED.value,
            change_type=ChangeType.CREATE.value,
            principal_id=principal_id,
            justification="create agent",
            schema_version=1,
        )
        return Agent(id=model.agent_id, name=model.name)

    async def list_agent_versions(
        self, *, tenant_id: UUID, agent_id: str, status_filter: list[str] | None = None
    ) -> list[AgentVersion]:
        agent_uuid = UUID(agent_id)
        agent = await self.repository.get_agent(agent_uuid)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        versions = await self.repository.list_agent_versions(
            agent_id=agent_uuid, status_filter=status_filter
        )
        result = []
        for version in versions:
            persona_config = None
            if version.persona_config:
                persona_config = PersonaConfig.model_validate(version.persona_config)
            result.append(
                AgentVersion(
                    id=version.agent_version_id,
                    agent_id=version.agent_id,
                    description=version.description,
                    status=version.status,
                    version_major=version.version_major,
                    version_minor=version.version_minor,
                    version_patch=version.version_patch,
                    config_hash=version.config_hash,
                    supported_tool_schema_version=version.supported_tool_schema_version,
                    supported_tool_config_hash_prefix=version.supported_tool_config_hash_prefix,
                    persona_config=persona_config,
                    system_prompt=version.system_prompt,
                )
            )
        return result

    async def create_agent_version(
        self,
        *,
        tenant_id: UUID,
        agent_id: str,
        agent_version_create: AgentVersionCreate,
        principal_id: str,
    ) -> AgentVersion:
        agent_uuid = UUID(agent_id)
        agent = await self.repository.get_agent(agent_uuid)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        persona_config_dict = None
        if agent_version_create.persona_config:
            persona_config_dict = agent_version_create.persona_config.model_dump()

        model = await self.repository.create_agent_version(
            agent_id=agent_uuid,
            source_version_id=agent_version_create.source_version_id,
            version_major=agent_version_create.version_major,
            version_minor=agent_version_create.version_minor,
            version_patch=agent_version_create.version_patch,
            description=agent_version_create.description,
            supported_tool_schema_version=agent_version_create.supported_tool_schema_version,
            supported_tool_config_hash_prefix=agent_version_create.supported_tool_config_hash_prefix,
            persona_config=persona_config_dict,
            system_prompt=agent_version_create.system_prompt,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="agent",
            resource_id=agent_uuid,
            version_id=model.agent_version_id,
            event_type=AuthoringEventType.AGENT_VERSION_CREATED.value,
            change_type=ChangeType.CREATE.value,
            principal_id=principal_id,
            justification="create agent version",
            schema_version=1,
        )
        persona_config = None
        if model.persona_config:
            persona_config = PersonaConfig.model_validate(model.persona_config)

        return AgentVersion(
            id=model.agent_version_id,
            agent_id=model.agent_id,
            description=model.description,
            status=model.status,
            version_major=model.version_major,
            version_minor=model.version_minor,
            version_patch=model.version_patch,
            config_hash=model.config_hash,
            supported_tool_schema_version=model.supported_tool_schema_version,
            supported_tool_config_hash_prefix=model.supported_tool_config_hash_prefix,
            persona_config=persona_config,
            system_prompt=model.system_prompt,
        )

    async def create_node_agent_binding(
        self,
        *,
        tenant_id: UUID,
        node_agent_binding_create: NodeAgentBindingCreate,
        principal_id: str,
    ) -> NodeAgentBinding:
        agent_version = await self.repository.get_agent_version(
            node_agent_binding_create.agent_version_id
        )
        if agent_version is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        agent = await self.repository.get_agent(agent_version.agent_id)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        model = await self.repository.create_node_agent_binding(
            node_id=node_agent_binding_create.node_id,
            agent_version_id=node_agent_binding_create.agent_version_id,
            created_by=principal_id,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="node_agent_binding",
            resource_id=model.node_agent_binding_id,
            version_id=None,
            event_type=AuthoringEventType.NODE_AGENT_BINDING_CREATED.value,
            change_type=ChangeType.CREATE.value,
            principal_id=principal_id,
            justification="create node agent binding",
            schema_version=1,
        )
        return NodeAgentBinding(
            id=model.node_agent_binding_id,
            node_id=model.node_id,
            agent_version_id=model.agent_version_id,
        )

    async def list_node_bindings_by_agent_version(
        self, *, tenant_id: UUID, agent_version_id: UUID
    ) -> list[NodeAgentBinding]:
        models = await self.repository.list_node_bindings_by_agent_version_id(
            tenant_id=tenant_id, agent_version_id=agent_version_id
        )
        return [
            NodeAgentBinding(
                id=m.node_agent_binding_id,
                node_id=m.node_id,
                agent_version_id=m.agent_version_id,
            )
            for m in models
        ]

    async def validate_agent_version(
        self, *, tenant_id: UUID, agent_id: str, agent_version_id: str
    ):
        agent_uuid = UUID(agent_id)
        version_uuid = UUID(agent_version_id)
        agent = await self.repository.get_agent(agent_uuid)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        version = await self.repository.get_agent_version(version_uuid)
        if version is None or version.agent_id != agent_uuid:
            raise NotFoundServiceException(message="agent_version_not_found")
        if version.status != VersionStatus.DRAFT:
            raise ResourceBlockedServiceException(message="agent_version_not_draft")
        await self.repository.set_agent_version_status(
            agent_version_id=version_uuid, status=VersionStatus.VALIDATED
        )
        refreshed = await self.repository.get_agent_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        return refreshed

    async def publish_agent_version(
        self,
        *,
        tenant_id: UUID,
        agent_id: str,
        agent_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ):
        agent_uuid = UUID(agent_id)
        version_uuid = UUID(agent_version_id)
        agent = await self.repository.get_agent(agent_uuid)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        version = await self.repository.get_agent_version(version_uuid)
        if version is None or version.agent_id != agent_uuid:
            raise NotFoundServiceException(message="agent_version_not_found")
        if version.status != VersionStatus.VALIDATED:
            raise ResourceBlockedServiceException(message="agent_version_not_validated")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.set_agent_version_status(
            agent_version_id=version_uuid, status=VersionStatus.PUBLISHED
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="agent",
            resource_id=agent_uuid,
            version_id=version_uuid,
            event_type=AuthoringEventType.VERSION_PUBLISHED.value,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        refreshed = await self.repository.get_agent_version(version_uuid)
        if refreshed is None:
            raise NotFoundServiceException(message="agent_version_not_found")
        return refreshed

    async def activate_agent_version(
        self,
        *,
        tenant_id: UUID,
        agent_id: str,
        agent_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ):
        agent_uuid = UUID(agent_id)
        version_uuid = UUID(agent_version_id)
        agent = await self.repository.get_agent(agent_uuid)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        version = await self.repository.get_agent_version(version_uuid)
        if version is None or version.agent_id != agent_uuid:
            raise NotFoundServiceException(message="agent_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="agent_version_not_published")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.upsert_active_agent_version(
            agent_id=agent_uuid,
            agent_version_id=version_uuid,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="agent",
            resource_id=agent_uuid,
            version_id=version_uuid,
            event_type=AuthoringEventType.VERSION_ACTIVATED.value,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        return version

    async def rollback_agent_version(
        self,
        *,
        tenant_id: UUID,
        agent_id: str,
        agent_version_id: str,
        principal_id: str,
        change_request: ChangeRequest,
    ):
        agent_uuid = UUID(agent_id)
        version_uuid = UUID(agent_version_id)
        agent = await self.repository.get_agent(agent_uuid)
        if agent is None or agent.tenant_id != tenant_id:
            raise NotFoundServiceException(message="agent_not_found")
        version = await self.repository.get_agent_version(version_uuid)
        if version is None or version.agent_id != agent_uuid:
            raise NotFoundServiceException(message="agent_version_not_found")
        if version.status != VersionStatus.PUBLISHED:
            raise ResourceBlockedServiceException(message="agent_version_not_published")
        if not change_request.justification.strip():
            raise DomainValidationException(message="justification_required")
        await self.repository.upsert_active_agent_version(
            agent_id=agent_uuid,
            agent_version_id=version_uuid,
            activated_by_principal_id=principal_id,
            justification=change_request.justification,
        )
        await self.authoring_events.append_event(
            tenant_id=tenant_id,
            resource_type="agent",
            resource_id=agent_uuid,
            version_id=version_uuid,
            event_type=AuthoringEventType.VERSION_ROLLED_BACK.value,
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        return version
