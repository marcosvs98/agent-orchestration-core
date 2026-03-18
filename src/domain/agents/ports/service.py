from abc import ABC, abstractmethod
from uuid import UUID

from exceptions.service_exceptions import NotImplementedServiceException


class AgentsServicePort(ABC):
    @abstractmethod
    async def list_agents(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_agent(self, agent_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_agent_versions(self, agent_id: UUID):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_agent_version(self, agent_id: UUID, agent_version_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_node_agent_binding(self, node_agent_binding_create):
        raise NotImplementedServiceException()

    @abstractmethod
    async def validate_agent_version(
        self, *, tenant_id, agent_id: UUID, agent_version_id: UUID
    ):
        raise NotImplementedServiceException()

    @abstractmethod
    async def publish_agent_version(
        self,
        *,
        tenant_id,
        agent_id: UUID,
        agent_version_id: UUID,
        principal_id: str,
        change_request,
    ):
        raise NotImplementedServiceException()

    @abstractmethod
    async def activate_agent_version(
        self,
        *,
        tenant_id,
        agent_id: UUID,
        agent_version_id: UUID,
        principal_id: str,
        change_request,
    ):
        raise NotImplementedServiceException()

    @abstractmethod
    async def rollback_agent_version(
        self,
        *,
        tenant_id,
        agent_id: UUID,
        agent_version_id: UUID,
        principal_id: str,
        change_request,
    ):
        raise NotImplementedServiceException()
