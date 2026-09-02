"""Runtime enforcement of the grant, at the moment a tool call arrives.

Resolving the grant is only half of the guarantee. These tests cover the other half: a call the
grant does not cover never becomes a ``tool_run``, and the model is told why.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.schemas.agent_run import DELEGATION_TOOL_NAME
from domain.execution.services.agent_runtime.tool_dispatcher import AgentToolDispatcher
from domain.execution.services.agent_runtime.tool_grant import ResolvedToolGrant
from domain.execution.services.agent_runtime.types import (
    AgentRunScope,
    AgentToolCallStatus,
)
from domain.llm.schemas.agent_turn import AgentToolCall
from tests.unit.pkg.domain.agent_runtime.conftest import build_tool


def _scope(tenant_id) -> AgentRunScope:
    agent_run_id = uuid4()
    return AgentRunScope(
        tenant_id=tenant_id,
        principal_id="principal",
        agent_run_id=agent_run_id,
        agent_id=uuid4(),
        correlation_id=uuid4(),
        root_agent_run_id=agent_run_id,
    )


def _dispatcher(tracer, *, tool_result: dict | None = None, tool_error: Exception | None = None):
    execution_repository = MagicMock()
    execution_repository.create_tool_run = AsyncMock(return_value=uuid4())
    tool_orchestrator = MagicMock()
    tool_orchestrator.execute_agent_tool_run = AsyncMock(
        return_value=tool_result or {"status_code": 200, "body": {"ok": True}},
        side_effect=tool_error,
    )
    delegation_service = MagicMock()
    dispatcher = AgentToolDispatcher(
        execution_repository=execution_repository,
        tool_orchestrator=tool_orchestrator,
        delegation_service=delegation_service,
        tracer=tracer,
    )
    return dispatcher, execution_repository, tool_orchestrator, delegation_service


@pytest.mark.asyncio
async def test_a_tool_outside_the_grant_is_denied_without_creating_a_tool_run(
    tracer, tenant_id
) -> None:
    dispatcher, execution_repository, tool_orchestrator, _ = _dispatcher(tracer)
    grant = ResolvedToolGrant(
        tools=[build_tool("search")], allow_agent_delegation=False, delegate_agent_ids=[]
    )

    outcome = await dispatcher.dispatch(
        scope=_scope(tenant_id),
        grant=grant,
        tool_call=AgentToolCall(call_id="c1", name="wire_transfer", arguments={}),
        runner=MagicMock(),
    )

    assert outcome.status is AgentToolCallStatus.DENIED
    assert outcome.error["error"] == "tool_not_authorized_for_this_run"
    execution_repository.create_tool_run.assert_not_awaited()
    tool_orchestrator.execute_agent_tool_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_denial_is_reported_back_to_the_model_as_a_readable_result(tracer, tenant_id) -> None:
    dispatcher, _, _, _ = _dispatcher(tracer)
    grant = ResolvedToolGrant(
        tools=[build_tool("search")], allow_agent_delegation=False, delegate_agent_ids=[]
    )

    outcome = await dispatcher.dispatch(
        scope=_scope(tenant_id),
        grant=grant,
        tool_call=AgentToolCall(call_id="c1", name="wire_transfer", arguments={}),
        runner=MagicMock(),
    )

    payload = json.loads(outcome.result_text)
    assert payload["error"] == "tool_not_authorized_for_this_run"
    assert payload["authorized_tools"] == ["search"]


@pytest.mark.asyncio
async def test_an_authorized_tool_runs_through_the_existing_tool_runtime(tracer, tenant_id) -> None:
    dispatcher, execution_repository, tool_orchestrator, _ = _dispatcher(tracer)
    tool = build_tool("search")
    grant = ResolvedToolGrant(tools=[tool], allow_agent_delegation=False, delegate_agent_ids=[])
    scope = _scope(tenant_id)

    outcome = await dispatcher.dispatch(
        scope=scope,
        grant=grant,
        tool_call=AgentToolCall(call_id="c1", name="search", arguments={"query": "uora"}),
        runner=MagicMock(),
    )

    assert outcome.status is AgentToolCallStatus.SUCCESS
    create_kwargs = execution_repository.create_tool_run.await_args.kwargs
    assert create_kwargs["tool_config_id"] == tool.tool_config_id
    assert create_kwargs["agent_run_id"] == scope.agent_run_id
    assert create_kwargs["node_run_id"] is None
    assert create_kwargs["tool_call_id"] == "c1"
    tool_orchestrator.execute_agent_tool_run.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_metadata_reaches_the_tool_header_resolver(tracer, tenant_id) -> None:
    """Tool configs may bind headers to run-scoped values.

    Without this the imported OpenAPI tools — whose auth header binds to interaction metadata —
    are unusable from an agent run, because a direct run carries no interaction.
    """

    dispatcher, _, tool_orchestrator, _ = _dispatcher(tracer)
    grant = ResolvedToolGrant(
        tools=[build_tool("search")], allow_agent_delegation=False, delegate_agent_ids=[]
    )
    scope = _scope(tenant_id).model_copy(
        update={"interaction_metadata": {"uora_end_user_authorization": "Bearer abc"}}
    )

    await dispatcher.dispatch(
        scope=scope,
        grant=grant,
        tool_call=AgentToolCall(call_id="c1", name="search", arguments={"query": "x"}),
        runner=MagicMock(),
    )

    kwargs = tool_orchestrator.execute_agent_tool_run.await_args.kwargs
    assert kwargs["interaction_metadata"] == {"uora_end_user_authorization": "Bearer abc"}
    assert kwargs["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_arguments_are_validated_before_any_side_effect(tracer, tenant_id) -> None:
    dispatcher, execution_repository, tool_orchestrator, _ = _dispatcher(tracer)
    grant = ResolvedToolGrant(
        tools=[build_tool("search")], allow_agent_delegation=False, delegate_agent_ids=[]
    )

    outcome = await dispatcher.dispatch(
        scope=_scope(tenant_id),
        grant=grant,
        tool_call=AgentToolCall(call_id="c1", name="search", arguments={"wrong": 1}),
        runner=MagicMock(),
    )

    assert outcome.status is AgentToolCallStatus.INVALID_ARGUMENTS
    execution_repository.create_tool_run.assert_not_awaited()
    tool_orchestrator.execute_agent_tool_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failing_tool_becomes_a_result_the_loop_can_continue_from(
    tracer, tenant_id
) -> None:
    dispatcher, _, _, _ = _dispatcher(tracer, tool_error=RuntimeError("upstream down"))
    grant = ResolvedToolGrant(
        tools=[build_tool("search")], allow_agent_delegation=False, delegate_agent_ids=[]
    )

    outcome = await dispatcher.dispatch(
        scope=_scope(tenant_id),
        grant=grant,
        tool_call=AgentToolCall(call_id="c1", name="search", arguments={"query": "x"}),
        runner=MagicMock(),
    )

    assert outcome.status is AgentToolCallStatus.ERROR
    assert outcome.tool_run_id is not None
    assert json.loads(outcome.result_text)["error"] == "tool_execution_failed"


@pytest.mark.asyncio
async def test_delegation_to_an_unauthorized_agent_is_denied(tracer, tenant_id) -> None:
    dispatcher, _, _, delegation_service = _dispatcher(tracer)
    delegation_service.delegate = AsyncMock()
    grant = ResolvedToolGrant(tools=[], allow_agent_delegation=True, delegate_agent_ids=[uuid4()])

    outcome = await dispatcher.dispatch(
        scope=_scope(tenant_id),
        grant=grant,
        tool_call=AgentToolCall(
            call_id="c1",
            name=DELEGATION_TOOL_NAME,
            arguments={"agent_id": str(uuid4()), "instruction": "do it"},
        ),
        runner=MagicMock(),
    )

    assert outcome.status is AgentToolCallStatus.DENIED
    assert outcome.error["error"] == "delegate_agent_not_authorized_for_this_run"
    delegation_service.delegate.assert_not_awaited()


@pytest.mark.asyncio
async def test_delegation_tool_is_only_offered_when_the_run_allows_it(tracer) -> None:
    dispatcher, _, _, _ = _dispatcher(tracer)
    delegate_agent_id = uuid4()

    without = dispatcher.build_tool_definitions(
        ResolvedToolGrant(
            tools=[build_tool("search")], allow_agent_delegation=False, delegate_agent_ids=[]
        )
    )
    with_delegation = dispatcher.build_tool_definitions(
        ResolvedToolGrant(
            tools=[build_tool("search")],
            allow_agent_delegation=True,
            delegate_agent_ids=[delegate_agent_id],
        )
    )

    assert [definition.name for definition in without] == ["search"]
    assert [definition.name for definition in with_delegation] == [
        "search",
        DELEGATION_TOOL_NAME,
    ]
    delegation_definition = with_delegation[-1]
    assert delegation_definition.parameters["properties"]["agent_id"]["enum"] == [
        str(delegate_agent_id)
    ]
