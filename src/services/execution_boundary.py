from uuid import UUID

from domain.governance.schemas.scopes import Scope
from domain.governance.services.access_policy_service import AccessPolicyService
from domain.governance.services.rate_limit_service import RateLimitService
from domain.execution.schemas.execution import (
    FlowRun,
    FlowRunCreate,
    ToolRun,
    ToolRunCreate,
    ExecutionEvent,
)
from domain.execution.services.execution_service import ExecutionService
from domain.tools.services.tool_orchestrator import ToolOrchestrator
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
        payload: FlowRunCreate,
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
            action=str(Scope.ExecutionFlowRunCreate),
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
            payload=payload,
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
        return await self.tool_orchestrator.execute_tool_run(tool_run_id=tool_run_id)

    async def create_tool_run(
        self,
        *,
        auth: AuthContext,
        endpoint: str,
        idempotency_key: str,
        payload: ToolRunCreate,
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
            payload=payload,
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
