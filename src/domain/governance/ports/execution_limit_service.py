from abc import ABC, abstractmethod
from uuid import UUID
from exceptions.service_exceptions import NotImplementedServiceException


class ExecutionLimitServicePort(ABC):
    @abstractmethod
    async def assert_can_create_agent_run(
        self, *, tenant_id: UUID, flow_run_id: UUID
    ) -> None:
        raise NotImplementedServiceException()

    @abstractmethod
    async def assert_can_create_tool_run(
        self, *, tenant_id: UUID, flow_run_id: UUID
    ) -> None:
        raise NotImplementedServiceException()
