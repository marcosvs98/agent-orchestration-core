from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.services.graph_runtime.nodes.fallback import FallbackNode
from domain.llm.schemas.llm import LLMResult
from domain.prompts.schemas.prompt import ResolvedPrompt
from domain.execution.services.graph_runtime.types import (
    ExecutionContext,
    NodeExecutionStatus,
)
from domain.human_sla.schemas.human_sla_policy import HumanSLAPolicy
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
        human_sla_policy_id=None,
        current_escalation_level=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_case_for_fallback_returns_case_id() -> None:
    case = _build_case_model()
    repository = AsyncMock()
    repository.create_case = AsyncMock(return_value=case)
    policy_repository = AsyncMock()
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

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
    policy_repository = AsyncMock()
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

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
    policy_repository = AsyncMock()
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=tenant_id,
        session_id=session_id,
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        node="IntentDetectionNode",
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
    policy_repository = AsyncMock()
    policy_repository.resolve_policy = AsyncMock(return_value=None)
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=tenant_id,
        session_id=session_id,
        flow_run_id=new_case.flow_run_id,
        node_run_id=new_case.node_run_id,
        interaction_id=None,
        user_id=new_case.user_id,
        node="IntentDetectionNode",
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        opened_at=new_case.opened_at,
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
    policy_repository = AsyncMock()
    policy_repository.resolve_policy = AsyncMock(return_value=None)
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=uuid4(),
        session_id=uuid4(),
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        node="ToolSelectionNode",
        fallback_reason=SLAFallbackReason.UNKNOWN_INTENT,
        opened_at=datetime.now(timezone.utc),
    )

    assert result is None
    repository.create_case.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_create_open_case_with_policy_sets_priority_sla_and_policy_id() -> None:
    tenant_id = uuid4()
    session_id = uuid4()
    policy_id = uuid4()
    opened_at = datetime.now(timezone.utc)
    policy = HumanSLAPolicy(
        human_sla_policy_id=policy_id,
        tenant_id=tenant_id,
        name="policy-a",
        node="ToolNode",
        fallback_reason="TOOL_FAILURE",
        initial_priority="high",
        target_response_hours=4,
        target_resolution_hours=24,
        active=True,
        created_at=opened_at,
        updated_at=opened_at,
        escalation_rules=[],
    )
    new_case = _build_case_model(status=SLAStatus.OPEN.value)
    new_case.priority = "high"
    new_case.human_sla_policy_id = policy_id
    new_case.current_escalation_level = 0
    new_case.sla_target_at = opened_at.replace(tzinfo=timezone.utc)
    repository = AsyncMock()
    repository.get_last_open_case_for_session = AsyncMock(return_value=None)
    repository.create_case = AsyncMock(return_value=new_case)
    policy_repository = AsyncMock()
    policy_repository.resolve_policy = AsyncMock(return_value=policy)
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

    result = await service.get_or_create_open_case_for_fallback(
        tenant_id=tenant_id,
        session_id=session_id,
        flow_run_id=uuid4(),
        node_run_id=uuid4(),
        interaction_id=None,
        user_id="user-1",
        node="ToolNode",
        fallback_reason=SLAFallbackReason.TOOL_FAILURE,
        opened_at=opened_at,
    )

    assert result is not None
    assert result.priority == "high"
    assert result.human_sla_policy_id == policy_id
    call_args = repository.create_case.await_args[0][0]
    assert call_args.priority == "high"
    assert call_args.human_sla_policy_id == policy_id
    assert call_args.current_escalation_level == 0
    assert call_args.sla_target_at is not None


@pytest.mark.asyncio
async def test_evaluate_sla_no_op_when_case_has_no_policy() -> None:
    case_id = uuid4()
    tenant_id = uuid4()
    case = _build_case_model()
    case.sla_case_id = case_id
    case.tenant_id = tenant_id
    case.human_sla_policy_id = None
    repository = AsyncMock()
    repository.get_case = AsyncMock(return_value=case)
    policy_repository = AsyncMock()
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

    await service.evaluate_sla(case_id=case_id, tenant_id=tenant_id)

    repository.get_case.assert_awaited_once_with(sla_case_id=case_id, tenant_id=tenant_id)
    policy_repository.get_policy_with_rules.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluate_sla_applies_escalation_and_marks_breached() -> None:
    from domain.human_sla.schemas.human_sla_policy import HumanSLAEscalationRule
    case_id = uuid4()
    tenant_id = uuid4()
    policy_id = uuid4()
    opened_at = datetime.now(timezone.utc) - timedelta(hours=2)
    case = _build_case_model()
    case.sla_case_id = case_id
    case.tenant_id = tenant_id
    case.human_sla_policy_id = policy_id
    case.current_escalation_level = 0
    case.opened_at = opened_at
    case.sla_breached = False
    rule = HumanSLAEscalationRule(
        human_sla_escalation_rule_id=uuid4(),
        human_sla_policy_id=policy_id,
        level=1,
        trigger_after_hours=0,
        new_priority="urgent",
    )
    policy = HumanSLAPolicy(
        human_sla_policy_id=policy_id,
        tenant_id=tenant_id,
        name="p",
        node="n",
        fallback_reason="TOOL_FAILURE",
        initial_priority="high",
        target_response_hours=4,
        target_resolution_hours=1,
        active=True,
        created_at=opened_at,
        updated_at=opened_at,
        escalation_rules=[rule],
    )
    repository = AsyncMock()
    repository.get_case = AsyncMock(return_value=case)
    repository.update_case_escalation = AsyncMock()
    repository.update_case_sla_breached = AsyncMock()
    policy_repository = AsyncMock()
    policy_repository.get_policy_with_rules = AsyncMock(return_value=policy)
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

    await service.evaluate_sla(case_id=case_id, tenant_id=tenant_id)

    repository.update_case_escalation.assert_awaited_once_with(
        sla_case_id=case_id,
        tenant_id=tenant_id,
        priority="urgent",
        level=1,
    )
    repository.update_case_sla_breached.assert_awaited_once_with(
        sla_case_id=case_id, tenant_id=tenant_id
    )


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
    policy_repository = AsyncMock()
    service = HumanSLAService(repository=repository, policy_repository=policy_repository)

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


def _make_fallback_node(human_sla_service=None, llm_output=None):
    tracer = MagicMock()
    tracer.observe = MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=None)))
    llm_executor = AsyncMock()
    llm_executor.execute_llm = AsyncMock(
        return_value=LLMResult(
            output=llm_output or {"fallback": {"sla_triggered": False, "ticket_id": None}},
            token_usage={},
        )
    )
    prompt_resolver = AsyncMock()
    prompt_resolver.resolve = AsyncMock(
        return_value=ResolvedPrompt(
            prompt_text="",
            input_schema={},
            output_schema={},
            prompt_id=None,
            prompt_version=None,
            prompt_frozen_hash="",
        )
    )
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
    node = _make_fallback_node(
        human_sla_service=human_sla_service,
        llm_output={
            "fallback": {
                "sla_triggered": True,
                "ticket_id": str(created_sla_case_id),
                "reason": "TOOL_FAILURE",
            }
        },
    )

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
        metadata={
            "fallback_source_node": "ToolSelectionNode",
            "fallback_reason": "TOOL_FAILURE",
            "operation_ids": ["op-1"],
        },
    )

    result = await node.execute(
        context,
        config={
            "llm": {"model_alias": "gpt-4"},
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

    result = await node.execute(context, config={"llm": {"model_alias": "gpt-4"}})

    assert result.status == NodeExecutionStatus.SUCCESS
    assert result.data["fallback"]["sla_triggered"] is False
    assert result.data["fallback"]["ticket_id"] is None
