from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.nodes.fallback import FallbackNode
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
)
from domain.human_sla.schemas.sla_case import (
    SLACaseResolve,
    SLAFallbackReason,
    SLAResolutionStatus,
    SLAStatus,
)
from domain.human_sla.services.human_sla_service import HumanSLAService


def _build_case_model(status: str = "OPEN") -> SimpleNamespace:
    return SimpleNamespace(
        sla_case_id=uuid4(),
        tenant_id=uuid4(),
        session_id=uuid4(),
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        status=status,
        priority="medium",
        fallback_reason="UNKNOWN_INTENT",
        human_agent_id=None,
        resolution_status=None,
        resolution_summary=None,
        opened_at=datetime.now(timezone.utc),
        assigned_at=None,
        resolved_at=None,
        sla_target_at=None,
        sla_breached=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_case_for_fallback_returns_case_id() -> None:
    case = _build_case_model()
    repository = AsyncMock()
    repository.create_case = AsyncMock(return_value=case)
    service = HumanSLAService(repository=repository)

    result = await service.create_case_for_fallback(
        tenant_id=case.tenant_id,
        session_id=case.session_id,
        flow_run_id=case.flow_run_id,
        node_run_id=case.node_run_id,
        interaction_id=case.interaction_id,
        user_id=case.user_id,
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        priority=case.priority,
        opened_at=case.opened_at,
    )

    assert result == case.sla_case_id
    repository.create_case.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_case_for_fallback_idempotent_returns_none() -> None:
    repository = AsyncMock()
    repository.create_case = AsyncMock(return_value=None)
    service = HumanSLAService(repository=repository)

    result = await service.create_case_for_fallback(
        tenant_id=uuid4(),
        session_id=uuid4(),
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        opened_at=datetime.now(timezone.utc),
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_or_create_open_case_returns_existing_when_open_exists() -> None:
    tenant_id = uuid4()
    session_id = uuid4()
    existing_case = _build_case_model(status=SLAStatus.OPEN.value)
    existing_case.tenant_id = tenant_id
    existing_case.session_id = session_id
    repository = AsyncMock()
    repository.get_last_open_case_for_session = AsyncMock(return_value=existing_case)
    repository.create_case = AsyncMock()
    service = HumanSLAService(repository=repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=tenant_id,
        session_id=session_id,
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        opened_at=existing_case.opened_at,
    )

    assert result is not None
    assert result.sla_case_id == existing_case.sla_case_id
    assert result.status == SLAStatus.OPEN
    repository.get_last_open_case_for_session.assert_awaited_once_with(
        tenant_id=tenant_id, session_id=session_id
    )
    repository.create_case.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_create_open_case_creates_when_no_open_exists() -> None:
    tenant_id = uuid4()
    session_id = uuid4()
    new_case = _build_case_model(status=SLAStatus.OPEN.value)
    new_case.priority = "high"
    repository = AsyncMock()
    repository.get_last_open_case_for_session = AsyncMock(return_value=None)
    repository.create_case = AsyncMock(return_value=new_case)
    service = HumanSLAService(repository=repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=tenant_id,
        session_id=session_id,
        flow_run_id=new_case.flow_run_id,
        node_run_id=new_case.node_run_id,
        interaction_id=None,
        user_id=new_case.user_id,
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        opened_at=new_case.opened_at,
        priority="high",
    )

    assert result is not None
    assert result.sla_case_id == new_case.sla_case_id
    assert result.priority == "high"
    repository.get_last_open_case_for_session.assert_awaited_once()
    repository.create_case.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_open_case_returns_none_when_create_conflicts() -> None:
    repository = AsyncMock()
    repository.get_last_open_case_for_session = AsyncMock(return_value=None)
    repository.create_case = AsyncMock(return_value=None)
    service = HumanSLAService(repository=repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=uuid4(),
        session_id=uuid4(),
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        opened_at=datetime.now(timezone.utc),
    )

    assert result is None
    repository.create_case.assert_awaited_once()


@pytest.mark.asyncio
async def test_assign_and_resolve_case_lifecycle() -> None:
    assigned_case = _build_case_model(status=SLAStatus.ASSIGNED.value)
    assigned_case.human_agent_id = "agent-1"
    assigned_case.assigned_at = datetime.now(timezone.utc)
    resolved_case = _build_case_model(status=SLAStatus.RESOLVED.value)
    resolved_case.human_agent_id = "agent-1"
    resolved_case.resolution_status = SLAResolutionStatus.RESOLVED.value
    resolved_case.resolution_summary = "resolved by human"
    resolved_case.resolved_at = datetime.now(timezone.utc)

    repository = AsyncMock()
    repository.assign_case = AsyncMock(return_value=assigned_case)
    repository.resolve_case = AsyncMock(return_value=resolved_case)
    service = HumanSLAService(repository=repository)

    assign_response = await service.assign_case(
        tenant_id=assigned_case.tenant_id,
        sla_case_id=assigned_case.sla_case_id,
        human_agent_id="agent-1",
    )
    resolve_response = await service.resolve_case(
        tenant_id=resolved_case.tenant_id,
        sla_case_id=resolved_case.sla_case_id,
        payload=SLACaseResolve(
            resolution_status=SLAResolutionStatus.RESOLVED,
            resolution_summary="resolved by human",
            human_agent_id="agent-1",
        ),
    )

    assert assign_response.status == SLAStatus.ASSIGNED
    assert assign_response.human_agent_id == "agent-1"
    assert resolve_response.status == SLAStatus.RESOLVED
    assert resolve_response.resolution_status == SLAResolutionStatus.RESOLVED
    assert resolve_response.resolution_summary == "resolved by human"


def _make_fallback_node(human_sla_service=None):
    tracer = MagicMock()
    tracer.observe = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=None)))
    llm_executor = AsyncMock()
    prompt_resolver = AsyncMock()
    return FallbackNode(
        tracer=tracer,
        llm_executor=llm_executor,
        prompt_resolver=prompt_resolver,
        human_sla_service=human_sla_service,
    )


@pytest.mark.asyncio
async def test_fallback_node_execute_with_service_creates_ticket() -> None:
    created_sla_case_id = uuid4()
    sla_response = _build_case_model(status=SLAStatus.OPEN.value)
    sla_response.sla_case_id = created_sla_case_id
    sla_response.priority = "high"
    human_sla_service = AsyncMock()
    human_sla_service.get_or_create_open_case_for_fallback = AsyncMock(
        return_value=sla_response
    )
    node = _make_fallback_node(human_sla_service=human_sla_service)

    context = ExecutionContext(
        tenant_id=uuid4(),
        interaction_id=uuid4(),
        user_id="user-1",
        session_id=uuid4(),
        input_payload={"user_input": "help"},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        current_node_id=str(uuid4()),
        current_node_run_id=uuid4(),
        metadata={"origin_node": "ToolExecutionNode", "operation_ids": ["op-1"]},
    )

    result = await node.execute(
        context,
        config={
            "fallback_reason": "TOOL_FAILURE",
            "severity": "high",
            "system_output": "human support required",
        },
    )

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["fallback"]["sla_triggered"] is True
    assert result.data["fallback"]["ticket_id"] == str(created_sla_case_id)
    assert result.data["fallback"]["reason"] == "TOOL_FAILURE"


@pytest.mark.asyncio
async def test_fallback_node_execute_without_service_returns_no_ticket() -> None:
    node = _make_fallback_node(human_sla_service=None)
    context = ExecutionContext(
        tenant_id=uuid4(),
        interaction_id=uuid4(),
        user_id="user-1",
        session_id=uuid4(),
        input_payload={"user_input": "help"},
        flow_id=uuid4(),
        flow_version_id=uuid4(),
        flow_run_id=uuid4(),
        correlation_id=uuid4(),
        current_node_id=str(uuid4()),
        current_node_run_id=uuid4(),
    )

    result = await node.execute(context, config={})

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["fallback"]["sla_triggered"] is False
    assert result.data["fallback"]["ticket_id"] is None
