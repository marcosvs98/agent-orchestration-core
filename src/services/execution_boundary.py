import contextlib
from uuid import UUID

from domain.governance.schemas.scopes import Scope
from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.services.rate_limit_service import RateLimitService
from domain.execution.schemas.execution import (
    AgentRun,
    FlowRun,
    FlowRunCreate,
    FlowRunInput,
    GraphState,
    NodeRun,
    ToolRun,
    ToolRunCreate,
    ExecutionEvent,
)
from domain.execution.services.execution_service import ExecutionService
from domain.tools.services.tool_orchestrator import ToolOrchestrator
from exceptions.service_exceptions import NotFoundServiceException
from utils.auth import AuthContext


class ExecutionBoundary:
    def __init__(
        self,
        execution_service: ExecutionService,
        tool_orchestrator: ToolOrchestrator,
        access_policy_service: AccessPolicyService,
        rate_limit_service: RateLimitService,
    ) -> None:
        self.execution_service = execution_service
        self.tool_orchestrator = tool_orchestrator
        self.access_policy_service = access_policy_service
        self.rate_limit_service = rate_limit_service

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
    ) -> FlowRun:
        tracer = self.execution_service.tracer
        guardrail_cm = (
            tracer.observe(
                as_type="guardrail",
                name="execution_boundary.rate_limit.enforce",
                input={
                    "tenant_id": str(auth.tenant_id),
                    "action": str(Scope.ExecutionFlowRunCreate),
                },
                metadata={"guardrail_type": "rate_limit"},
            )
            if tracer
            else contextlib.nullcontext()
        )
        with guardrail_cm:
            await self.rate_limit_service.enforce(
                tenant_id=auth.tenant_id,
                principal_type=auth.principal_type,
                principal_id=auth.principal_id,
                action=Scope.ExecutionFlowRunCreate,
            )

        access_cm = (
            tracer.observe(
                as_type="guardrail",
                name="execution_boundary.access_policy.authorize",
                input={
                    "tenant_id": str(auth.tenant_id),
                    "action": str(Scope.ExecutionFlowRunCreate),
                },
                metadata={"guardrail_type": "access_policy"},
            )
            if tracer
            else contextlib.nullcontext()
        )
        with access_cm:
            await self.access_policy_service.authorize(
                tenant_id=auth.tenant_id,
                principal_type=auth.principal_type,
                principal_id=auth.principal_id,
                scopes=auth.scopes,
                action=str(Scope.ExecutionFlowRunCreate),
            )

        span_cm = (
            tracer.observe(
                as_type="span",
                name="execution_boundary.create_flow_run",
                input={
                    "tenant_id": str(auth.tenant_id),
                    "endpoint": endpoint,
                },
            )
            if tracer
            else contextlib.nullcontext()
        )
        with span_cm:
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
                user_id=str(auth.tenant_id),
            )

    async def resume_flow_run(
        self,
        *,
        auth: AuthContext,
        flow_run_id: UUID,
        input_payload: FlowRunInput | None,
        channel: str,
        headers: dict[str, str],
        external_message_id: str | None,
        request_id: str | None,
        trace_id: str | None,
    ) -> FlowRun:
        tracer = self.execution_service.tracer
        guardrail_cm = (
            tracer.observe(
                as_type="guardrail",
                name="execution_boundary.rate_limit.enforce_resume",
                input={
                    "tenant_id": str(auth.tenant_id),
                    "action": str(Scope.ExecutionFlowRunResume),
                },
                metadata={"guardrail_type": "rate_limit"},
            )
            if tracer
            else contextlib.nullcontext()
        )
        with guardrail_cm:
            await self.rate_limit_service.enforce(
                tenant_id=auth.tenant_id,
                principal_type=auth.principal_type,
                principal_id=auth.principal_id,
                action=Scope.ExecutionFlowRunResume,
            )

        access_cm = (
            tracer.observe(
                as_type="guardrail",
                name="execution_boundary.access_policy.authorize_resume",
                input={
                    "tenant_id": str(auth.tenant_id),
                    "action": str(Scope.ExecutionFlowRunResume),
                },
                metadata={"guardrail_type": "access_policy"},
            )
            if tracer
            else contextlib.nullcontext()
        )
        with access_cm:
            await self.access_policy_service.authorize(
                tenant_id=auth.tenant_id,
                principal_type=auth.principal_type,
                principal_id=auth.principal_id,
                scopes=auth.scopes,
                action=str(Scope.ExecutionFlowRunResume),
            )

        span_cm = (
            tracer.observe(
                as_type="span",
                name="execution_boundary.resume_flow_run",
                input={
                    "tenant_id": str(auth.tenant_id),
                    "flow_run_id": str(flow_run_id),
                },
            )
            if tracer
            else contextlib.nullcontext()
        )
        with span_cm:
            return await self.execution_service.resume_flow_run(
                flow_run_id=flow_run_id,
                input_payload=input_payload,
                channel=channel,
                headers=headers,
                external_message_id=external_message_id,
                request_id=request_id,
                trace_id=trace_id,
                user_id=str(auth.tenant_id),
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
        return await self.execution_service.list_execution_events(
            flow_run_id=flow_run_id, correlation_id=correlation_id, limit=limit
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
            session_id,
            tenant_id,
        ) = await self.execution_service.repository.get_flow_context(UUID(flow_run_id))
        if tenant_id != auth.tenant_id:
            raise NotFoundServiceException(message="flow_run_not_found")
        return flow_run

    async def get_graph_state(
        self, *, auth: AuthContext, flow_run_id: str
    ) -> GraphState:
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
            session_id,
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
        flow_run_uuid = UUID(flow_run_id) if flow_run_id else None
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
        flow_run_uuid = UUID(flow_run_id) if flow_run_id else None
        return await self.execution_service.list_agent_runs(
            tenant_id=auth.tenant_id, flow_run_id=flow_run_uuid, limit=limit
        )
