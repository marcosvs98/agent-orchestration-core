"""Behavioural unit tests for execution HTTP controllers (mocked Request / boundary)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import Request

from domain.execution.controllers.execution_controller import ExecutionController
from domain.execution.controllers.execution_plane_controller import (
    ExecutionPlaneController,
)
from domain.execution.ports.runtime_tracer import RuntimeTracerPort
from domain.execution.schemas.execution import (
    ExecutionEvent,
    FlowRun,
    FlowRunCreate,
    FlowRunResumeInput,
    GraphState,
    ToolRun,
    ToolRunCreate,
)
from exceptions.service_exceptions import (
    MethodNotAllowedPlaceholderException,
    RouterValidationException,
)
from services.execution_boundary import ExecutionBoundary
from utils.auth import AuthContext


def _tracer() -> MagicMock:
    t = MagicMock(spec=RuntimeTracerPort)
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


def _auth() -> AuthContext:
    return MagicMock(spec=AuthContext)


def _flow_run_create() -> FlowRunCreate:
    return FlowRunCreate(
        flow_id=uuid4(),
        session_id=uuid4(),
        user_id="user",
        metadata={},
    )


@pytest.mark.asyncio
async def test_execution_controller_create_flow_run_requires_idempotency() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.trace_id = None
    req.headers = {}
    req.url.path = "/core/v1/flow-runs"

    with pytest.raises(RouterValidationException):
        await ctrl.create_flow_run(
            request=req,
            flow_run=_flow_run_create(),
            auth=_auth(),
            idempotency_key=None,
        )


@pytest.mark.asyncio
async def test_execution_controller_create_flow_run_delegates_to_boundary() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    expected = MagicMock(spec=FlowRun)
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(return_value=expected)
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.trace_id = None
    req.headers = MagicMock()
    req.headers.get = MagicMock(return_value=None)
    req.url.path = "/core/v1/flow-runs"

    out = await ctrl.create_flow_run(
        request=req,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem-1",
    )
    assert out is expected
    boundary.ingest_interaction_and_create_flow_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_execution_plane_controller_create_flow_run_success() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    expected = MagicMock(spec=FlowRun)
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(return_value=expected)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.headers = MagicMock()
    req.headers.get = MagicMock(side_effect=lambda k, d=None: None)
    req.url.path = "/core/v1/executions/flow-runs"

    out = await ctrl.create_flow_run(
        request=req,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="k",
    )
    assert out is expected
    call_kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert call_kw["channel"] == "http"


@pytest.mark.asyncio
async def test_execution_plane_get_flow_run_delegates_to_boundary() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    expected = MagicMock(spec=FlowRun)
    boundary.get_flow_run = AsyncMock(return_value=expected)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    fid = uuid4()
    out = await ctrl.get_flow_run(fid, _auth())
    assert out is expected
    boundary.get_flow_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_execution_controller_deprecated_read_endpoints_raise_placeholder() -> (
    None
):
    ctrl = ExecutionController(
        boundary=MagicMock(spec=ExecutionBoundary), tracer=_tracer()
    )
    with pytest.raises(MethodNotAllowedPlaceholderException):
        await ctrl.get_graph_state(str(uuid4()), _auth())
    with pytest.raises(MethodNotAllowedPlaceholderException):
        await ctrl.list_node_runs(_auth())
    with pytest.raises(MethodNotAllowedPlaceholderException):
        await ctrl.list_agent_runs(_auth())


@pytest.mark.asyncio
async def test_execution_controller_get_flow_run_raises_placeholder() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    with pytest.raises(MethodNotAllowedPlaceholderException):
        await ctrl.get_flow_run(str(uuid4()), _auth())


@pytest.mark.asyncio
async def test_execution_controller_create_tool_run_requires_idempotency() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.url.path = "/x"
    with pytest.raises(RouterValidationException):
        await ctrl.create_tool_run(
            request=req,
            tool_run=ToolRunCreate(tool_config_id=uuid4()),
            auth=_auth(),
            idempotency_key=None,
        )


@pytest.mark.asyncio
async def test_execution_controller_create_flow_run_invalid_trace_uses_32_hex() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(
        return_value=MagicMock(spec=FlowRun)
    )
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    hex32 = "a" * 32
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.trace_id = None
    req.headers = MagicMock()
    req.headers.get = MagicMock(
        side_effect=lambda k, d=None: hex32 if k == "X-Trace-Id" else None
    )
    req.url.path = "/core/v1/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem",
    )
    kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert kw["trace_id"] == str(UUID(hex=hex32))


@pytest.mark.asyncio
async def test_execution_controller_create_flow_run_uses_x_trace_id_header() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(
        return_value=MagicMock(spec=FlowRun)
    )
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.trace_id = None
    req.headers = MagicMock()
    req.headers.get = MagicMock(side_effect=lambda k, d=None: str(tid) if k == "X-Trace-Id" else None)
    req.url.path = "/core/v1/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem",
    )
    kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert kw["trace_id"] == str(tid)


@pytest.mark.asyncio
async def test_execution_controller_create_flow_run_prefers_request_state_trace() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(
        return_value=MagicMock(spec=FlowRun)
    )
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.trace_id = tid
    req.headers = MagicMock()
    req.headers.get = MagicMock(return_value="ignored")
    req.url.path = "/core/v1/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem",
    )
    kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert kw["trace_id"] == str(tid)


@pytest.mark.asyncio
async def test_execution_controller_create_tool_run_and_execute_delegate() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    tr = MagicMock(spec=ToolRun)
    boundary.create_tool_run = AsyncMock(return_value=tr)
    boundary.execute_tool_run = AsyncMock(return_value={"ok": True})
    ctrl = ExecutionController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.url.path = "/tool-runs"
    out = await ctrl.create_tool_run(
        request=req,
        tool_run=ToolRunCreate(tool_config_id=uuid4()),
        auth=_auth(),
        idempotency_key="k",
    )
    assert out is tr
    rid = uuid4()
    ex = await ctrl.execute_tool_run(str(rid), _auth())
    assert ex == {"ok": True}
    boundary.execute_tool_run.assert_awaited_once()
    assert boundary.execute_tool_run.await_args.kwargs["tool_run_id"] == rid


@pytest.mark.asyncio
async def test_execution_plane_create_flow_run_x_trace_id() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(
        return_value=MagicMock(spec=FlowRun)
    )
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": str(tid)}
    req.url.path = "/core/v1/executions/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem",
    )
    kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert kw["trace_id"] == str(tid)


@pytest.mark.asyncio
async def test_execution_plane_resume_flow_run_propagates_trace() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.resume_flow_run = AsyncMock(return_value=MagicMock(spec=FlowRun))
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    fr_id = uuid4()
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": str(tid)}
    req.url.path = "/resume"

    await ctrl.resume_flow_run(
        request=req,
        flow_run_id=str(fr_id),
        payload=FlowRunResumeInput(user_id="u1"),
        auth=_auth(),
    )
    kw = boundary.resume_flow_run.await_args.kwargs
    assert kw["trace_id"] == str(tid)
    assert kw["flow_run_id"] == fr_id


@pytest.mark.asyncio
async def test_execution_plane_create_tool_run_and_execute_delegate() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    tr = MagicMock(spec=ToolRun)
    boundary.create_tool_run = AsyncMock(return_value=tr)
    boundary.execute_tool_run = AsyncMock(return_value={"done": True})
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.url.path = "/tool-runs"
    out = await ctrl.create_tool_run(
        request=req,
        payload=ToolRunCreate(tool_config_id=uuid4()),
        auth=_auth(),
        idempotency_key="k",
    )
    assert out is tr
    ex = await ctrl.execute_tool_run(str(uuid4()), _auth())
    assert ex == {"done": True}


@pytest.mark.asyncio
async def test_execution_plane_get_graph_state_and_lists_delegate() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    gs = MagicMock(spec=GraphState)
    boundary.get_graph_state = AsyncMock(return_value=gs)
    boundary.list_node_runs = AsyncMock(return_value=[])
    boundary.list_agent_runs = AsyncMock(return_value=[])
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    fid = uuid4()
    assert await ctrl.get_graph_state(fid, _auth()) is gs
    assert await ctrl.list_node_runs(flow_run_id=str(fid), auth=_auth()) == []
    assert await ctrl.list_agent_runs(flow_run_id=None, auth=_auth()) == []


@pytest.mark.asyncio
async def test_execution_plane_list_execution_events_filters_by_tenant() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    auth = _auth()
    same = uuid4()
    auth.tenant_id = same
    other = uuid4()
    e1 = MagicMock(spec=ExecutionEvent)
    e1.tenant_id = same
    e2 = MagicMock(spec=ExecutionEvent)
    e2.tenant_id = other
    boundary.list_execution_events = AsyncMock(return_value=[e1, e2])
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    fr = uuid4()
    out = await ctrl.list_execution_events(
        flow_run_id=str(fr), correlation_id=None, limit=10, auth=auth
    )
    assert out == [e1]


@pytest.mark.asyncio
async def test_execution_plane_list_execution_events_invalid_uuid() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    with pytest.raises(RouterValidationException):
        await ctrl.list_execution_events(
            flow_run_id="not-a-uuid",
            correlation_id=None,
            limit=10,
            auth=_auth(),
        )


@pytest.mark.asyncio
async def test_execution_plane_missing_idempotency_tool_run() -> None:
    ctrl = ExecutionPlaneController(
        boundary=MagicMock(spec=ExecutionBoundary), tracer=_tracer()
    )
    req = MagicMock(spec=Request)
    req.url.path = "/t"
    with pytest.raises(RouterValidationException):
        await ctrl.create_tool_run(
            request=req,
            payload=ToolRunCreate(tool_config_id=uuid4()),
            auth=_auth(),
            idempotency_key=None,
        )
