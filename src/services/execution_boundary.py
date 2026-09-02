from uuid import UUID

from domain.governance.schemas.scopes import Scope
from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.services.rate_limit_service import RateLimitService
from domain.execution.schemas.execution import (
    AgentRun,
    FlowRun,
    FlowRunCreate,
    FlowRunResumeInput,
    GraphState,
    NodeRun,
    ToolRun,
    ToolRunCreate,
    ExecutionEvent,
)
from domain.execution.schemas.agent_run import (
    AgentRunCreate,
    AgentRunDetail,
    AgentRunSummary,
)
from domain.execution.services.agent_run_service import AgentRunService
from domain.execution.services.execution_service import ExecutionService
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from exceptions.service_exceptions import (
    DomainValidationException,
    NotFoundServiceException,
)
from utils.auth import AuthContext


class ExecutionBoundary:
    def __init__(
        self,
        execution_service: ExecutionService,
        agent_run_service: AgentRunService,
        tool_orchestrator: ToolOrchestrator,
        access_policy_service: AccessPolicyService,
        rate_limit_service: RateLimitService,
    ) -> None:
        self.execution_service = execution_service
        self.agent_run_service = agent_run_service
        self.tool_orchestrator = tool_orchestrator
        self.access_policy_service = access_policy_service
        self.rate_limit_service = rate_limit_service

    async def _authorize(self, *, auth: AuthContext, action: Scope) -> None:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(action),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(action),
        )

    async def create_agent_run(
        self,
        *,
        auth: AuthContext,
        endpoint: str,
        idempotency_key: str,
        agent_run: AgentRunCreate,
        wait: bool,
    ) -> AgentRunSummary:
        await self._authorize(auth=auth, action=Scope.ExecutionAgentRunCreate)
        return await self.agent_run_service.create_agent_run(
            tenant_id=auth.tenant_id,
            principal_id=auth.principal_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request=agent_run,
            wait=wait,
        )

    async def get_agent_run(self, *, auth: AuthContext, agent_run_id: UUID) -> AgentRunDetail:
        await self._authorize(auth=auth, action=Scope.ExecutionAgentRunGet)
        return await self.agent_run_service.get_agent_run(
            tenant_id=auth.tenant_id, agent_run_id=agent_run_id
        )

    async def list_agent_run_summaries(
        self,
        *,
        auth: AuthContext,
        agent_id: UUID | None = None,
        flow_run_id: UUID | None = None,
        root_agent_run_id: UUID | None = None,
        parent_agent_run_id: UUID | None = None,
        limit: int = 200,
    ) -> list[AgentRunSummary]:
        await self._authorize(auth=auth, action=Scope.ExecutionAgentRunsList)
        return await self.agent_run_service.list_agent_runs(
            tenant_id=auth.tenant_id,
            agent_id=agent_id,
            flow_run_id=flow_run_id,
            root_agent_run_id=root_agent_run_id,
            parent_agent_run_id=parent_agent_run_id,
            limit=limit,
        )

    async def cancel_agent_run(self, *, auth: AuthContext, agent_run_id: UUID) -> AgentRunSummary:
        await self._authorize(auth=auth, action=Scope.ExecutionAgentRunCancel)
        return await self.agent_run_service.cancel_agent_run(
            tenant_id=auth.tenant_id, agent_run_id=agent_run_id
        )

    async def _assert_flow_run_tenant(self, *, auth: AuthContext, flow_run_id: UUID) -> None:
        _, tenant_id = await self.execution_service.repository.get_flow_context(flow_run_id)
        if tenant_id != auth.tenant_id:
            raise NotFoundServiceException(message="flow_run_not_found")

    async def _assert_tool_run_tenant(self, *, auth: AuthContext, tool_run_id: UUID) -> None:
        repository = self.execution_service.repository
        tool_run = await repository.get_tool_run(tool_run_id)
        if tool_run is None:
            raise NotFoundServiceException(message="tool_run_not_found")
        node_run_id = tool_run.node_run_id
        if node_run_id is None and tool_run.agent_run_id is not None:
            agent_run = await repository.get_agent_run(tool_run.agent_run_id)
            node_run_id = agent_run.node_run_id if agent_run is not None else None
        if node_run_id is None:
            raise NotFoundServiceException(message="tool_run_not_found")
        node_run = await repository.get_node_run(node_run_id)
        if node_run is None:
            raise NotFoundServiceException(message="tool_run_not_found")
        try:
            await self._assert_flow_run_tenant(auth=auth, flow_run_id=node_run.flow_run_id)
        except NotFoundServiceException as exc:
            raise NotFoundServiceException(message="tool_run_not_found") from exc

    async def ingest_interaction_and_create_flow_run(
        self,
        *,
        auth: AuthContext,
        endpoint: str,
        idempotency_key: str,
        flow_run: FlowRunCreate,
        channel: str,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
        wait: bool = False,
    ) -> FlowRun:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=Scope.ExecutionFlowRunCreate,
        )

        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionFlowRunCreate),
        )

        return await self.execution_service.create_flow_run(
            tenant_id=auth.tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            flow_run=flow_run,
            channel=channel,
            headers=headers,
            external_message_id=external_message_id,
            request_id=request_id,
            trace_id=trace_id,
            wait=wait,
        )

    async def resume_flow_run(
        self,
        *,
        auth: AuthContext,
        flow_run_id: UUID,
        input_payload: FlowRunResumeInput | None,
        channel: str,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
    ) -> FlowRun:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=Scope.ExecutionFlowRunResume,
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionFlowRunResume),
        )
        await self._assert_flow_run_tenant(auth=auth, flow_run_id=flow_run_id)
        return await self.execution_service.resume_flow_run(
            flow_run_id=flow_run_id,
            input_payload=input_payload,
            channel=channel,
            headers=headers,
            external_message_id=external_message_id,
            request_id=request_id,
            trace_id=trace_id,
        )

    async def execute_tool_run(self, *, auth: AuthContext, tool_run_id: UUID) -> dict:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionToolRunExecute),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionToolRunExecute),
        )
        await self._assert_tool_run_tenant(auth=auth, tool_run_id=tool_run_id)
        return await self.tool_orchestrator.execute_tool_run(tool_run_id=tool_run_id)

    async def create_tool_run(
        self,
        *,
        auth: AuthContext,
        endpoint: str,
        idempotency_key: str,
        tool_run: ToolRunCreate,
    ) -> ToolRun:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionToolRunCreate),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionToolRunCreate),
        )
        return await self.execution_service.create_tool_run(
            tenant_id=auth.tenant_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            tool_run=tool_run,
        )

    async def list_execution_events(
        self,
        *,
        flow_run_id: UUID | None = None,
        correlation_id: UUID | None = None,
        limit: int = 200,
        auth: AuthContext,
    ) -> list[ExecutionEvent]:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionEventsList),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionEventsList),
        )
        if flow_run_id is not None:
            await self._assert_flow_run_tenant(auth=auth, flow_run_id=flow_run_id)
        return await self.execution_service.list_execution_events(
            tenant_id=auth.tenant_id,
            flow_run_id=flow_run_id,
            correlation_id=correlation_id,
            limit=limit,
        )

    async def get_flow_run(self, *, auth: AuthContext, flow_run_id: str) -> FlowRun:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionFlowRunGet),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionFlowRunGet),
        )
        flow_run = await self.execution_service.get_flow_run(flow_run_id)
        (
            _,
            tenant_id,
        ) = await self.execution_service.repository.get_flow_context(UUID(flow_run_id))
        if tenant_id != auth.tenant_id:
            raise NotFoundServiceException(message="flow_run_not_found")
        return flow_run

    async def get_graph_state(self, *, auth: AuthContext, flow_run_id: str) -> GraphState:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionGraphStateGet),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionGraphStateGet),
        )
        (
            _,
            tenant_id,
        ) = await self.execution_service.repository.get_flow_context(UUID(flow_run_id))
        if tenant_id != auth.tenant_id:
            raise NotFoundServiceException(message="flow_run_not_found")
        return await self.execution_service.get_graph_state(flow_run_id)

    async def list_node_runs(
        self,
        *,
        auth: AuthContext,
        flow_run_id: str | None = None,
        limit: int = 200,
    ) -> list[NodeRun]:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionNodeRunsList),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionNodeRunsList),
        )
        try:
            flow_run_uuid = UUID(flow_run_id) if flow_run_id else None
        except (ValueError, TypeError) as e:
            raise DomainValidationException(
                message="Invalid flow_run_id format; expected UUID."
            ) from e
        return await self.execution_service.list_node_runs(
            tenant_id=auth.tenant_id, flow_run_id=flow_run_uuid, limit=limit
        )

    async def list_agent_runs(
        self,
        *,
        auth: AuthContext,
        flow_run_id: str | None = None,
        limit: int = 200,
    ) -> list[AgentRun]:
        await self.rate_limit_service.enforce(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            action=str(Scope.ExecutionAgentRunsList),
        )
        await self.access_policy_service.authorize(
            tenant_id=auth.tenant_id,
            principal_type=auth.principal_type,
            principal_id=auth.principal_id,
            scopes=auth.scopes,
            action=str(Scope.ExecutionAgentRunsList),
        )
        try:
            flow_run_uuid = UUID(flow_run_id) if flow_run_id else None
        except (ValueError, TypeError) as e:
            raise DomainValidationException(
                message="Invalid flow_run_id format; expected UUID."
            ) from e
        return await self.execution_service.list_agent_runs(
            tenant_id=auth.tenant_id, flow_run_id=flow_run_uuid, limit=limit
        )
