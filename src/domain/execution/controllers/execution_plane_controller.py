from fastapi import APIRouter, Depends, Header, Query, Request, status
from uuid import UUID, uuid4

from domain.execution.ports.runtime_tracer import RuntimeTracerPort
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
from services.execution_boundary import ExecutionBoundary
from domain.common.schemas.error import ErrorResponse
from exceptions.service_exceptions import (
    RouterValidationException,
)
from utils.auth import AuthContext, get_auth_context


class ExecutionPlaneController:
    """HTTP controller for runtime execution plane (/core/v1/executions)."""

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
            "/flow-runs",
            self.create_flow_run,
            methods=["POST"],
            response_model=FlowRun,
            status_code=status.HTTP_201_CREATED,
            responses=self._resp405(),
        )
        r(
            "/tool-runs",
            self.create_tool_run,
            methods=["POST"],
            response_model=ToolRun,
            status_code=status.HTTP_201_CREATED,
            responses=self._resp405(),
        )
        r(
            "/tool-runs/{tool_run_id}:execute",
            self.execute_tool_run,
            methods=["POST"],
            response_model=dict,
            responses=self._resp405(),
        )
        r(
            "/flow-runs/{flow_run_id}",
            self.get_flow_run,
            methods=["GET"],
            response_model=FlowRun,
        )
        r(
            "/flow-runs/{flow_run_id}:resume",
            self.resume_flow_run,
            methods=["POST"],
            response_model=FlowRun,
            responses=self._resp405(),
        )
        r(
            "/flow-runs/{flow_run_id}/graph-state",
            self.get_graph_state,
            methods=["GET"],
            response_model=GraphState,
        )
        r(
            "/node-runs",
            self.list_node_runs,
            methods=["GET"],
            response_model=list[NodeRun],
        )
        r(
            "/agent-runs",
            self.list_agent_runs,
            methods=["GET"],
            response_model=list[AgentRun],
        )
        r(
            "/execution-events",
            self.list_execution_events,
            methods=["GET"],
            response_model=list[ExecutionEvent],
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

        trace_id_header = request.headers.get("X-Trace-Id")
        if trace_id_header:
            try:
                trace_uuid = UUID(trace_id_header)
            except ValueError:
                trace_uuid = (
                    UUID(hex=trace_id_header) if len(trace_id_header) == 32 else uuid4()
                )
        else:
            trace_uuid = uuid4()
        trace_id_str = str(trace_uuid)
        trace_id_hex = trace_uuid.hex

        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.create_flow_run",
            input={"endpoint": request.url.path, "idempotency_key": idempotency_key},
            trace_context={"trace_id": trace_id_hex},
        ) as span_handle:
            flow_run = await self.boundary.ingest_interaction_and_create_flow_run(
                auth=auth,
                endpoint=request.url.path,
                idempotency_key=idempotency_key,
                flow_run=flow_run,
                channel="http",
                headers=dict(request.headers),
                external_message_id=request.headers.get("X-External-Message-Id"),
                request_id=request.headers.get("X-Request-Id"),
                trace_id=trace_id_str,
            )
            if span_handle:
                span_handle.success(output=flow_run.model_dump(mode="json"))
            return flow_run

    async def create_tool_run(
        self,
        request: Request,
        payload: ToolRunCreate,
        auth: AuthContext = Depends(get_auth_context),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> ToolRun:
        if not idempotency_key:
            raise RouterValidationException(errors=["missing_idempotency_key"])
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.create_tool_run",
            input={"endpoint": request.url.path},
        ):
            return await self.boundary.create_tool_run(
                auth=auth,
                endpoint=request.url.path,
                idempotency_key=idempotency_key,
                payload=payload,
            )

    async def execute_tool_run(
        self, tool_run_id: str, auth: AuthContext = Depends(get_auth_context)
    ) -> dict:
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.execute_tool_run",
            input={"tool_run_id": tool_run_id},
        ):
            return await self.boundary.execute_tool_run(
                auth=auth, tool_run_id=UUID(tool_run_id)
            )

    async def get_flow_run(
        self, flow_run_id: str, auth: AuthContext = Depends(get_auth_context)
    ) -> FlowRun:
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.get_flow_run",
            input={"flow_run_id": flow_run_id},
        ):
            return await self.boundary.get_flow_run(auth=auth, flow_run_id=flow_run_id)

    async def resume_flow_run(
        self,
        request: Request,
        flow_run_id: str,
        payload: FlowRunResumeInput,
        auth: AuthContext = Depends(get_auth_context),
    ) -> FlowRun:
        trace_id_header = request.headers.get("X-Trace-Id")
        if trace_id_header:
            try:
                trace_uuid = UUID(trace_id_header)
            except ValueError:
                trace_uuid = (
                    UUID(hex=trace_id_header) if len(trace_id_header) == 32 else uuid4()
                )
        else:
            trace_uuid = uuid4()
        trace_id_str = str(trace_uuid)
        trace_id_hex = trace_uuid.hex

        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.resume_flow_run",
            input={"flow_run_id": flow_run_id, "endpoint": request.url.path},
            trace_context={"trace_id": trace_id_hex},
        ):
            return await self.boundary.resume_flow_run(
                auth=auth,
                flow_run_id=UUID(flow_run_id),
                input_payload=payload,
                channel="http",
                headers=dict(request.headers),
                external_message_id=request.headers.get("X-External-Message-Id"),
                request_id=request.headers.get("X-Request-Id"),
                trace_id=trace_id_str,
            )

    async def get_graph_state(
        self, flow_run_id: str, auth: AuthContext = Depends(get_auth_context)
    ) -> GraphState:
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.get_graph_state",
            input={"flow_run_id": flow_run_id},
        ):
            return await self.boundary.get_graph_state(
                auth=auth, flow_run_id=flow_run_id
            )

    async def list_node_runs(
        self,
        flow_run_id: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[NodeRun]:
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.list_node_runs",
            input={"flow_run_id": flow_run_id, "limit": limit},
        ):
            return await self.boundary.list_node_runs(
                auth=auth, flow_run_id=flow_run_id, limit=limit
            )

    async def list_agent_runs(
        self,
        flow_run_id: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=1000),
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[AgentRun]:
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.list_agent_runs",
            input={"flow_run_id": flow_run_id, "limit": limit},
        ):
            return await self.boundary.list_agent_runs(
                auth=auth, flow_run_id=flow_run_id, limit=limit
            )

    async def list_execution_events(
        self,
        flow_run_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 200,
        auth: AuthContext = Depends(get_auth_context),
    ) -> list[ExecutionEvent]:
        with self.tracer.observe(
            as_type="span",
            name="domain.execution.plane_controller.list_execution_events",
            input={
                "flow_run_id": flow_run_id,
                "correlation_id": correlation_id,
                "limit": limit,
            },
        ):
            flow_uuid = UUID(flow_run_id) if flow_run_id else None
            corr_uuid = UUID(correlation_id) if correlation_id else None
            events = await self.boundary.list_execution_events(
                flow_run_id=flow_uuid,
                correlation_id=corr_uuid,
                limit=limit,
                auth=auth,
            )
            return [e for e in events if e.tenant_id == auth.tenant_id]
