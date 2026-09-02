"""HTTP surface: idempotency, async signalling, and the A2A server methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import Response, status

from domain.agents.controllers.a2a_controller import A2AController
from domain.agents.schemas.a2a import A2AErrorCode, JsonRpcRequest
from domain.agents.services.a2a_translator import A2ATranslator
from domain.execution.controllers.agent_run_controller import AgentRunController
from domain.execution.schemas.agent_run import (
    AgentRunCreate,
    AgentRunDetail,
    AgentRunOrigin,
    AgentRunSummary,
)
from domain.execution.services.state_machine import AgentRunStatus
from exceptions.service_exceptions import RouterValidationException
from services.execution_boundary import ExecutionBoundary


def _auth(tenant_id) -> MagicMock:
    return MagicMock(
        tenant_id=tenant_id,
        principal_type="machine",
        principal_id="p",
        scopes={"execution:agent_run:create"},
    )


def _summary(tenant_id, canonical_status: str) -> AgentRunSummary:
    agent_run_id = uuid4()
    return AgentRunSummary(
        id=agent_run_id,
        tenant_id=tenant_id,
        agent_id=uuid4(),
        agent_version_id=uuid4(),
        origin=AgentRunOrigin.DIRECT,
        status=canonical_status,
        canonical_status=canonical_status,
        correlation_id=uuid4(),
        root_agent_run_id=agent_run_id,
    )


def _request() -> MagicMock:
    request = MagicMock()
    request.url.path = "/core/v1/executions/agent-runs"
    return request


@pytest.mark.asyncio
async def test_create_requires_an_idempotency_key(tracer, tenant_id) -> None:
    controller = AgentRunController(boundary=MagicMock(spec=ExecutionBoundary), tracer=tracer)

    with pytest.raises(RouterValidationException):
        await controller.create_agent_run(
            request=_request(),
            response=Response(),
            agent_run=AgentRunCreate(agent_id=uuid4(), instruction="do it"),
            auth=_auth(tenant_id),
            idempotency_key=None,
            wait=True,
        )


@pytest.mark.asyncio
async def test_a_completed_run_answers_201(tracer, tenant_id) -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.create_agent_run = AsyncMock(
        return_value=_summary(tenant_id, AgentRunStatus.COMPLETED.value)
    )
    controller = AgentRunController(boundary=boundary, tracer=tracer)
    response = Response()

    await controller.create_agent_run(
        request=_request(),
        response=response,
        agent_run=AgentRunCreate(agent_id=uuid4(), instruction="do it"),
        auth=_auth(tenant_id),
        idempotency_key="k1",
        wait=True,
    )

    assert response.status_code != status.HTTP_202_ACCEPTED


@pytest.mark.asyncio
async def test_a_still_running_submission_answers_202(tracer, tenant_id) -> None:
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.create_agent_run = AsyncMock(
        return_value=_summary(tenant_id, AgentRunStatus.RUNNING.value)
    )
    controller = AgentRunController(boundary=boundary, tracer=tracer)
    response = Response()

    await controller.create_agent_run(
        request=_request(),
        response=response,
        agent_run=AgentRunCreate(agent_id=uuid4(), instruction="do it"),
        auth=_auth(tenant_id),
        idempotency_key="k1",
        wait=False,
    )

    assert response.status_code == status.HTTP_202_ACCEPTED


def _detail(tenant_id) -> AgentRunDetail:
    agent_run_id = uuid4()
    return AgentRunDetail(
        id=agent_run_id,
        tenant_id=tenant_id,
        agent_id=uuid4(),
        agent_version_id=uuid4(),
        origin=AgentRunOrigin.DIRECT,
        status=AgentRunStatus.COMPLETED.value,
        canonical_status=AgentRunStatus.COMPLETED.value,
        correlation_id=uuid4(),
        root_agent_run_id=agent_run_id,
        output={"text": "done"},
    )


def _a2a_controller(boundary, tracer) -> A2AController:
    agent_card_service = MagicMock()
    return A2AController(
        boundary=boundary,
        agent_card_service=agent_card_service,
        translator=A2ATranslator(),
    )


@pytest.mark.asyncio
async def test_message_send_creates_a_run_and_answers_with_an_a2a_task(tracer, tenant_id) -> None:
    detail = _detail(tenant_id)
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.create_agent_run = AsyncMock(
        return_value=_summary(tenant_id, AgentRunStatus.COMPLETED.value)
    )
    boundary.get_agent_run = AsyncMock(return_value=detail)
    controller = _a2a_controller(boundary, tracer)

    result = await controller.handle_json_rpc(
        agent_id=uuid4(),
        rpc=JsonRpcRequest(
            jsonrpc="2.0",
            id=1,
            method="message/send",
            params={
                "message": {
                    "kind": "message",
                    "messageId": "m-1",
                    "role": "user",
                    "parts": [{"kind": "text", "text": "summarise this"}],
                }
            },
        ),
        auth=_auth(tenant_id),
    )

    assert result.error is None
    assert result.result["kind"] == "task"
    assert result.result["id"] == str(detail.id)
    assert result.result["status"]["state"] == "completed"
    created = boundary.create_agent_run.await_args.kwargs
    assert created["agent_run"].instruction == "summarise this"
    assert created["wait"] is True


@pytest.mark.asyncio
async def test_a_message_without_text_is_an_invalid_params_error(tracer, tenant_id) -> None:
    controller = _a2a_controller(MagicMock(spec=ExecutionBoundary), tracer)

    result = await controller.handle_json_rpc(
        agent_id=uuid4(),
        rpc=JsonRpcRequest(
            jsonrpc="2.0", id=1, method="message/send", params={"message": {"kind": "message"}}
        ),
        auth=_auth(tenant_id),
    )

    assert result.error is not None
    assert result.error.code == int(A2AErrorCode.INVALID_PARAMS)


@pytest.mark.asyncio
async def test_an_unknown_method_is_reported_as_method_not_found(tracer, tenant_id) -> None:
    controller = _a2a_controller(MagicMock(spec=ExecutionBoundary), tracer)

    result = await controller.handle_json_rpc(
        agent_id=uuid4(),
        rpc=JsonRpcRequest(jsonrpc="2.0", id=1, method="message/stream", params={}),
        auth=_auth(tenant_id),
    )

    assert result.error is not None
    assert result.error.code == int(A2AErrorCode.METHOD_NOT_FOUND)


@pytest.mark.asyncio
async def test_tasks_get_reads_the_run_behind_the_task_id(tracer, tenant_id) -> None:
    detail = _detail(tenant_id)
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.get_agent_run = AsyncMock(return_value=detail)
    controller = _a2a_controller(boundary, tracer)

    result = await controller.handle_json_rpc(
        agent_id=uuid4(),
        rpc=JsonRpcRequest(jsonrpc="2.0", id=1, method="tasks/get", params={"id": str(detail.id)}),
        auth=_auth(tenant_id),
    )

    assert result.result["id"] == str(detail.id)
    assert boundary.get_agent_run.await_args.kwargs["agent_run_id"] == detail.id


@pytest.mark.asyncio
async def test_tasks_cancel_cancels_the_underlying_run(tracer, tenant_id) -> None:
    detail = _detail(tenant_id)
    boundary = MagicMock(spec=ExecutionBoundary)
    boundary.cancel_agent_run = AsyncMock(
        return_value=_summary(tenant_id, AgentRunStatus.CANCELLED.value)
    )
    boundary.get_agent_run = AsyncMock(return_value=detail)
    controller = _a2a_controller(boundary, tracer)

    await controller.handle_json_rpc(
        agent_id=uuid4(),
        rpc=JsonRpcRequest(
            jsonrpc="2.0", id=1, method="tasks/cancel", params={"id": str(detail.id)}
        ),
        auth=_auth(tenant_id),
    )

    boundary.cancel_agent_run.assert_awaited_once()
