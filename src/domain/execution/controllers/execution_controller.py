from fastapi import APIRouter, Depends, Header, Request, status
from uuid import UUID

from domain.execution.schemas.execution import (
    AgentRun,
    FlowRun,
    FlowRunCreate,
    GraphState,
    NodeRun,
    ToolRun,
    ToolRunCreate,
)
from services.execution_boundary import ExecutionBoundary
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import (
    MethodNotAllowedPlaceholderException,
    RouterValidationException,
)
from utils.auth import AuthContext, get_auth_context


class ExecutionController:
    """HTTP controller for runtime execution."""

    def __init__(self, boundary: ExecutionBoundary) -> None:
        self.boundary = boundary
        self.router = APIRouter(
            prefix="/core/v1",  # Todo: Prefixos de API podem ser StrEnums
            tags=["execution"],  # Todo: Tasgs de API podem ser StrEnum's
            dependencies=[Depends(get_auth_context)],
        )
        self._bind_routes()

    def _bind_routes(self) -> None:
        r = self.router.add_api_route
        r(
            "/flow-runs",
            self.create_flow_run,
            methods=["POST"],
            response_model=FlowRun,
            status_code=status.HTTP_201_CREATED,
            deprecated=True,
            responses=self._resp405(),
        )
        r(
            "/tool-runs",
            self.create_tool_run,
            methods=["POST"],
            response_model=ToolRun,
            status_code=status.HTTP_201_CREATED,
            deprecated=True,
            responses=self._resp405(),
        )
        r(
            "/tool-runs/{tool_run_id}:execute",
            self.execute_tool_run,
            methods=["POST"],
            response_model=dict,
            deprecated=True,
            responses=self._resp405(),
        )
        r(
            "/flow-runs/{flow_run_id}",
            self.get_flow_run,
            methods=["GET"],
            response_model=FlowRun,
            deprecated=True,
            responses=self._resp405(),
        )
        r(
            "/flow-runs/{flow_run_id}/graph-state",
            self.get_graph_state,
            methods=["GET"],
            response_model=GraphState,
            deprecated=True,
            responses=self._resp405(),
        )
        r(
            "/node-runs",
            self.list_node_runs,
            methods=["GET"],
            response_model=list[NodeRun],
            deprecated=True,
            responses=self._resp405(),
        )
        r(
            "/agent-runs",
            self.list_agent_runs,
            methods=["GET"],
            response_model=list[AgentRun],
            deprecated=True,
            responses=self._resp405(),
        )

    def _resp405(self) -> dict[int, dict[str, object]]:
        return {status.HTTP_405_METHOD_NOT_ALLOWED: {"model": ErrorResponse}}

    async def create_flow_run(
        self,
        request: Request,
        flow_run: FlowRunCreate,
        auth: AuthContext = Depends(get_auth_context),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> FlowRun:
        if not idempotency_key:
            raise RouterValidationException(errors=["missing_idempotency_key"])
        return await self.boundary.ingest_interaction_and_create_flow_run(
            auth=auth,
            endpoint=request.url.path,
            idempotency_key=idempotency_key,
            flow_run=flow_run,
            channel="http",  # Todo: Channel pode ser StrEnum e Deveria vir na requisição
            headers=dict(request.headers),
            external_message_id=request.headers.get("X-External-Message-Id"),
            request_id=request.headers.get("X-Request-Id"),
            trace_id=request.headers.get("X-Trace-Id"),
        )

    async def create_tool_run(
        self,
        request: Request,
        tool_run: ToolRunCreate,
        auth: AuthContext = Depends(get_auth_context),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> ToolRun:
        if not idempotency_key:
            raise RouterValidationException(errors=["missing_idempotency_key"])
        return await self.boundary.create_tool_run(
            auth=auth,
            endpoint=request.url.path,
            idempotency_key=idempotency_key,
            tool_run=tool_run,
        )

    async def execute_tool_run(
        self, tool_run_id: str, auth: AuthContext = Depends(get_auth_context)
    ) -> dict:
        return await self.boundary.execute_tool_run(
            auth=auth, tool_run_id=UUID(tool_run_id)
        )

    async def get_flow_run(
        self, flow_run_id: str, _: AuthContext = Depends(get_auth_context)
    ) -> FlowRun:
        raise MethodNotAllowedPlaceholderException()

    async def get_graph_state(
        self, flow_run_id: str, _: AuthContext = Depends(get_auth_context)
    ) -> GraphState:
        raise MethodNotAllowedPlaceholderException()

    async def list_node_runs(
        self, _: AuthContext = Depends(get_auth_context)
    ) -> list[NodeRun]:
        raise MethodNotAllowedPlaceholderException()

    async def list_agent_runs(
        self, _: AuthContext = Depends(get_auth_context)
    ) -> list[AgentRun]:
        raise MethodNotAllowedPlaceholderException()
