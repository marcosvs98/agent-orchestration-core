"""Behavioural unit tests for execution HTTP controllers (mocked Request / boundary)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID, uuid4

import pytest
from fastapi import Request, Response

from domain.execution.services.state_machine import RunStatus

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
from exceptions.service_exceptions import RouterValidationException
from services.execution_boundary import ExecutionBoundary
from utils.auth import AuthContext


def _tracer() -> MagicMock:
    t = MagicMock(spec=RuntimeTracerPort)
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


def _auth() -> AuthContext:
    auth = MagicMock(spec=AuthContext)
    auth.tenant_id = uuid4()
    return auth


def _flow_run_create() -> FlowRunCreate:
    return FlowRunCreate(
        flow_id=uuid4(),
        session_id=uuid4(),
        user_id="user",
        metadata={},
    )


async def test_execution_plane_controller_create_flow_run_success() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    expected = MagicMock()
    expected.status = RunStatus.COMPLETED
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(return_value=expected)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.headers = MagicMock()
    req.headers.get = MagicMock(side_effect=lambda k, d=None: None)
    req.url.path = "/core/v1/executions/flow-runs"

    response = Response()
    out = await ctrl.create_flow_run(
        request=req,
        response=response,
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="k",
        wait=False,
    )
    assert out is expected
    assert response.status_code != 202
    call_kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert call_kw["channel"] == "http"
    assert call_kw["wait"] is False


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


async def test_execution_plane_create_flow_run_x_trace_id() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    queued = MagicMock()
    queued.status = RunStatus.QUEUED
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(return_value=queued)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": str(tid)}
    req.url.path = "/core/v1/executions/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        response=Response(),
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
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    fid = uuid4()
    assert await ctrl.get_graph_state(fid, _auth()) is gs
    assert await ctrl.list_node_runs(flow_run_id=str(fid), auth=_auth()) == []


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
    ctrl = ExecutionPlaneController(boundary=MagicMock(spec=ExecutionBoundary), tracer=_tracer())
    req = MagicMock(spec=Request)
    req.url.path = "/t"
    with pytest.raises(RouterValidationException):
        await ctrl.create_tool_run(
            request=req,
            payload=ToolRunCreate(tool_config_id=uuid4()),
            auth=_auth(),
            idempotency_key=None,
        )


@pytest.mark.asyncio
async def test_execution_plane_create_flow_run_32_hex_trace_id() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    queued = MagicMock()
    queued.status = RunStatus.QUEUED
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(return_value=queued)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": tid.hex}
    req.url.path = "/core/v1/executions/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        response=Response(),
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem",
    )
    kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert kw["trace_id"] == str(tid)


@pytest.mark.asyncio
async def test_execution_plane_create_flow_run_unparseable_trace_id_is_replaced() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    queued = MagicMock()
    queued.status = RunStatus.QUEUED
    boundary.ingest_interaction_and_create_flow_run = AsyncMock(return_value=queued)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": "not-a-trace-id"}
    req.url.path = "/core/v1/executions/flow-runs"

    await ctrl.create_flow_run(
        request=req,
        response=Response(),
        flow_run=_flow_run_create(),
        auth=_auth(),
        idempotency_key="idem",
    )
    kw = boundary.ingest_interaction_and_create_flow_run.await_args.kwargs
    assert UUID(kw["trace_id"])


@pytest.mark.asyncio
async def test_execution_plane_resume_flow_run_32_hex_trace_id() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.resume_flow_run = AsyncMock(return_value=MagicMock(spec=FlowRun))
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    tid = uuid4()
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": tid.hex}
    req.url.path = "/resume"

    await ctrl.resume_flow_run(
        request=req,
        flow_run_id=str(uuid4()),
        payload=FlowRunResumeInput(user_id="u1"),
        auth=_auth(),
    )
    assert boundary.resume_flow_run.await_args.kwargs["trace_id"] == str(tid)


@pytest.mark.asyncio
async def test_execution_plane_resume_flow_run_without_trace_header() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.resume_flow_run = AsyncMock(return_value=MagicMock(spec=FlowRun))
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.headers = {}
    req.url.path = "/resume"

    await ctrl.resume_flow_run(
        request=req,
        flow_run_id=str(uuid4()),
        payload=FlowRunResumeInput(user_id="u1"),
        auth=_auth(),
    )
    assert UUID(boundary.resume_flow_run.await_args.kwargs["trace_id"])


@pytest.mark.asyncio
async def test_execution_plane_create_flow_run_requires_idempotency() -> None:
    ctrl = ExecutionPlaneController(boundary=MagicMock(spec=ExecutionBoundary), tracer=_tracer())
    req = MagicMock(spec=Request)
    req.headers = {}
    req.url.path = "/core/v1/executions/flow-runs"

    with pytest.raises(RouterValidationException):
        await ctrl.create_flow_run(
            request=req,
            response=Response(),
            flow_run=_flow_run_create(),
            auth=_auth(),
            idempotency_key=None,
        )


@pytest.mark.asyncio
async def test_execution_plane_resume_flow_run_unparseable_trace_id_is_replaced() -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.resume_flow_run = AsyncMock(return_value=MagicMock(spec=FlowRun))
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.headers = {"X-Trace-Id": "zz" * 16}
    req.url.path = "/resume"

    await ctrl.resume_flow_run(
        request=req,
        flow_run_id=str(uuid4()),
        payload=FlowRunResumeInput(user_id="u1"),
        auth=_auth(),
    )
    assert UUID(boundary.resume_flow_run.await_args.kwargs["trace_id"])


@pytest.mark.asyncio
async def test_execution_plane_create_tool_run_matches_boundary_signature() -> None:
    boundary = create_autospec(ExecutionBoundary, instance=True)
    boundary.create_tool_run.return_value = MagicMock(spec=ToolRun)
    ctrl = ExecutionPlaneController(boundary=boundary, tracer=_tracer())
    req = MagicMock(spec=Request)
    req.url.path = "/core/v1/executions/tool-runs"

    await ctrl.create_tool_run(
        request=req,
        payload=ToolRunCreate(tool_config_id=uuid4()),
        auth=_auth(),
        idempotency_key="k",
    )
    assert "tool_run" in boundary.create_tool_run.await_args.kwargs
