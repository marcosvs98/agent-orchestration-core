from abc import ABC, abstractmethod
from uuid import UUID

from domain.execution.schemas.execution import (
    AgentRun,
    AgentRunCreate,
    FlowRun,
    FlowRunCreate,
    ToolRun,
    ToolRunCreate,
)
from exceptions.service_exceptions import NotImplementedServiceException


class ExecutionServicePort(ABC):
    @abstractmethod
    async def create_flow_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        flow_run: FlowRunCreate,
        channel: str = "http",
        headers: dict[str, str] | None = None,
        external_message_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> FlowRun:
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_flow_run(self, flow_run_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def get_graph_state(self, flow_run_id: str):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_node_runs(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_agent_runs(self):
        raise NotImplementedServiceException()

    @abstractmethod
    async def list_execution_events(
        self,
        *,
        flow_run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 200,
    ):
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_agent_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        payload: AgentRunCreate,
    ) -> AgentRun:
        raise NotImplementedServiceException()

    @abstractmethod
    async def complete_agent_run(
        self,
        *,
        agent_run_id: UUID,
        raw_output: dict,
        output_schema: type | None = None,
        metrics: dict | None = None,
    ) -> AgentRun:
        raise NotImplementedServiceException()

    @abstractmethod
    async def create_tool_run(
        self,
        *,
        tenant_id: UUID,
        endpoint: str,
        idempotency_key: str,
        payload: ToolRunCreate,
    ) -> ToolRun:
        raise NotImplementedServiceException()
