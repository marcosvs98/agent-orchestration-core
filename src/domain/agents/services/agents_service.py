from uuid import UUID

from domain.agents.ports.service import AgentsServicePort
from domain.agents.repositories.agents_repository import AgentsRepository
from domain.common.schemas.change import ChangeRequest
from domain.common.schemas.versioning import VersionStatus
from domain.governance.repositories.authoring_event_repository import AuthoringEventRepository
from exceptions.service_exceptions import (
    DomainValidationException,
    MethodNotAllowedPlaceholderException,
    NotFoundServiceException,
    ResourceBlockedServiceException,
)


class AgentsService(AgentsServicePort):
    def __init__(self, repository: AgentsRepository, authoring_events: AuthoringEventRepository) -> None:
        self.repository = repository
        self.authoring_events = authoring_events

    async def list_agents(self):
        raise MethodNotAllowedPlaceholderException()

    async def create_agent(self, agent_create):
        raise MethodNotAllowedPlaceholderException()

    async def list_agent_versions(self, agent_id: str):
        raise MethodNotAllowedPlaceholderException()

    async def create_agent_version(self, agent_id: str, agent_version_create):
        raise MethodNotAllowedPlaceholderException()

    async def create_node_agent_binding(self, node_agent_binding_create):
        raise MethodNotAllowedPlaceholderException()

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
            event_type="VERSION_PUBLISHED",
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
            event_type="VERSION_ACTIVATED",
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
            event_type="VERSION_ROLLED_BACK",
            change_type=change_request.change_type,
            principal_id=principal_id,
            justification=change_request.justification,
            schema_version=1,
        )
        return version
