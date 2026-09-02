from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from domain.common.schemas.error import ErrorResponse
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.agent_run import (
    AgentRunCreate,
    AgentRunDetail,
    AgentRunSummary,
)
from domain.execution.services.state_machine import AgentRunStatus
from exceptions.service_exceptions import RouterValidationException
from services.execution_boundary import ExecutionBoundary
from utils.auth import AuthContext, get_auth_context


class AgentRunController:
    """HTTP surface for agent executions (/core/v1/executions/agent-runs)."""

    def __init__(self, boundary: ExecutionBoundary, tracer: RuntimeTracerPort) -> None:
        self.boundary = boundary
        self.tracer = tracer
        self.router = APIRouter(
            prefix="/core/v1/executions",
            tags=["execution"],
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/agent-runs",
            self.create_agent_run,
            methods=["POST"],
            response_model=AgentRunSummary,
            status_code=status.HTTP_201_CREATED,
            responses={
                status.HTTP_202_ACCEPTED: {"model": AgentRunSummary},
                status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
                status.HTTP_409_CONFLICT: {"model": ErrorResponse},
            },
        )
        r(
            "/agent-runs",
            self.list_agent_runs,
            methods=["GET"],
            response_model=list[AgentRunSummary],
        )
        r(
            "/agent-runs/{agent_run_id}",
            self.get_agent_run,
            methods=["GET"],
            response_model=AgentRunDetail,
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
        )
        r(
            "/agent-runs/{agent_run_id}:cancel",
            self.cancel_agent_run,
            methods=["POST"],
            response_model=AgentRunSummary,
            responses={
                status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
                status.HTTP_409_CONFLICT: {"model": ErrorResponse},
            },
        )

    async def create_agent_run(
        self,
        request: Request,
        response: Response,
        agent_run: AgentRunCreate,
        auth: AuthContext = Depends(get_auth_context),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        wait: bool = Query(
            default=True,
            description="Block until the run reaches a terminal state.",
        ),
    ) -> AgentRunSummary:
        if not idempotency_key:
            raise RouterValidationException(errors=["missing_idempotency_key"])
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.agent_run_controller.create_agent_run",
            metadata={"tenant_id": str(auth.tenant_id)},
            input={
                "endpoint": request.url.path,
                "agent_id": str(agent_run.agent_id),
                "wait": wait,
            },
        ) as span_handle:
            created = await self.boundary.create_agent_run(
                auth=auth,
                endpoint=request.url.path,
                idempotency_key=idempotency_key,
                agent_run=agent_run,
                wait=wait,
            )
            if created.canonical_status in {
                AgentRunStatus.CREATED.value,
                AgentRunStatus.RUNNING.value,
            }:
                response.status_code = status.HTTP_202_ACCEPTED
            if span_handle:
                span_handle.success(output=created.model_dump(mode="json"))
            return created

    async def list_agent_runs(
        self,
        agent_id: UUID | None = Query(default=None),
        flow_run_id: UUID | None = Query(default=None),
        root_agent_run_id: UUID | None = Query(default=None),
        parent_agent_run_id: UUID | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[AgentRunSummary]:
        return await self.boundary.list_agent_run_summaries(
            auth=auth,
            agent_id=agent_id,
            flow_run_id=flow_run_id,
            root_agent_run_id=root_agent_run_id,
            parent_agent_run_id=parent_agent_run_id,
            limit=limit,
        )

    async def get_agent_run(
        self, agent_run_id: UUID, auth: AuthContext = Depends(get_auth_context)
    ) -> AgentRunDetail:
        return await self.boundary.get_agent_run(auth=auth, agent_run_id=agent_run_id)

    async def cancel_agent_run(
        self, agent_run_id: UUID, auth: AuthContext = Depends(get_auth_context)
    ) -> AgentRunSummary:
        return await self.boundary.cancel_agent_run(auth=auth, agent_run_id=agent_run_id)
