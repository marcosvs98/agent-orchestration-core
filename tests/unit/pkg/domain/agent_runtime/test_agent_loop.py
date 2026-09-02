"""The cognitive cycle: LLM → tool call → tool result → LLM → … → final output.

The loop is what makes an agent run more than one request/response pair, and the iteration bound
is what keeps a model that never stops asking for tools from running forever.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from domain.execution.schemas.agent_run import AgentRunFinishReason
from domain.execution.schemas.events import ExecutionEventType
from domain.execution.services.agent_runtime.agent_loop import AgentCognitiveLoop
from domain.execution.services.agent_runtime.context_builder import AgentRunContextBuilder
from domain.execution.services.agent_runtime.tool_grant import ResolvedToolGrant
from domain.execution.services.agent_runtime.types import (
    AgentRunScope,
    AgentToolCallStatus,
    ToolCallOutcome,
)
from domain.llm.schemas.agent_turn import (
    AgentToolCall,
    AgentTurnCompletion,
    AgentTurnRole,
    AgentTurnStopReason,
)
from exceptions.service_exceptions import DomainValidationException
from tests.unit.pkg.domain.agent_runtime.conftest import build_definition, build_tool


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


def _agent_run_repository() -> MagicMock:
    repository = MagicMock()
    repository.append_message = AsyncMock(return_value=1)
    repository.append_event = AsyncMock(return_value=1)
    repository.append_artifact = AsyncMock(return_value=1)
    return repository


def _execution_repository() -> MagicMock:
    repository = MagicMock()
    repository.record_llm_usage = AsyncMock(return_value=uuid4())
    return repository


def _dispatcher(outcomes: list[ToolCallOutcome]) -> MagicMock:
    dispatcher = MagicMock()
    dispatcher.build_tool_definitions = MagicMock(return_value=[])
    dispatcher.dispatch = AsyncMock(side_effect=outcomes)
    return dispatcher


def _completion(text: str = "", tool_calls: list[AgentToolCall] | None = None):
    calls = tool_calls or []
    return AgentTurnCompletion(
        text=text,
        tool_calls=calls,
        stop_reason=AgentTurnStopReason.TOOL_CALLS if calls else AgentTurnStopReason.OUTPUT,
        token_usage={"input_tokens": 10, "output_tokens": 5},
        model_alias="gpt-4.1",
    )


def _tool_outcome(call_id: str = "c1") -> ToolCallOutcome:
    return ToolCallOutcome(
        tool_call_id=call_id,
        function_name="search",
        status=AgentToolCallStatus.SUCCESS,
        result_text='{"body": {"answer": 42}}',
        tool_run_id=uuid4(),
    )


def _loop(agent_llm, dispatcher, agent_run_repository, tracer) -> AgentCognitiveLoop:
    return AgentCognitiveLoop(
        agent_llm=agent_llm,
        dispatcher=dispatcher,
        agent_run_repository=agent_run_repository,
        execution_repository=_execution_repository(),
        tracer=tracer,
        cost_engine=None,
    )


def _prompt_parts(definition, grant):
    return AgentRunContextBuilder().build(
        definition=definition,
        grant=grant,
        context_items=[],
        instruction="answer the question",
        payload={},
    )


@pytest.mark.asyncio
async def test_a_turn_without_tool_calls_finishes_the_run(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    grant = ResolvedToolGrant(
        tools=definition.tools, allow_agent_delegation=False, delegate_agent_ids=[]
    )
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="the answer"))

    result = await _loop(agent_llm, _dispatcher([]), _agent_run_repository(), tracer).run(
        scope=_scope(tenant_id),
        definition=definition,
        grant=grant,
        prompt_parts=_prompt_parts(definition, grant),
        max_iterations=5,
        runner=MagicMock(),
    )

    assert result.finish_reason is AgentRunFinishReason.FINAL_OUTPUT
    assert result.output_text == "the answer"
    assert result.iterations_used == 1
    assert agent_llm.complete_agent_turn.await_count == 1


@pytest.mark.asyncio
async def test_a_tool_call_feeds_its_result_back_into_the_next_turn(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    grant = ResolvedToolGrant(
        tools=definition.tools, allow_agent_delegation=False, delegate_agent_ids=[]
    )
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(
        side_effect=[
            _completion(tool_calls=[AgentToolCall(call_id="c1", name="search", arguments={})]),
            _completion(text="42"),
        ]
    )

    result = await _loop(
        agent_llm, _dispatcher([_tool_outcome()]), _agent_run_repository(), tracer
    ).run(
        scope=_scope(tenant_id),
        definition=definition,
        grant=grant,
        prompt_parts=_prompt_parts(definition, grant),
        max_iterations=5,
        runner=MagicMock(),
    )

    assert result.finish_reason is AgentRunFinishReason.FINAL_OUTPUT
    assert result.iterations_used == 2
    assert result.tool_call_count == 1
    second_turn = agent_llm.complete_agent_turn.await_args_list[1].kwargs["request"]
    roles = [message.role for message in second_turn.messages]
    assert AgentTurnRole.ASSISTANT in roles
    assert roles[-1] is AgentTurnRole.TOOL
    assert second_turn.messages[-1].tool_call_id == "c1"


@pytest.mark.asyncio
async def test_the_loop_stops_at_the_iteration_bound(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    grant = ResolvedToolGrant(
        tools=definition.tools, allow_agent_delegation=False, delegate_agent_ids=[]
    )
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(
        return_value=_completion(
            text="still working",
            tool_calls=[AgentToolCall(call_id="c1", name="search", arguments={})],
        )
    )
    dispatcher = MagicMock()
    dispatcher.build_tool_definitions = MagicMock(return_value=[])
    dispatcher.dispatch = AsyncMock(return_value=_tool_outcome())

    result = await _loop(agent_llm, dispatcher, _agent_run_repository(), tracer).run(
        scope=_scope(tenant_id),
        definition=definition,
        grant=grant,
        prompt_parts=_prompt_parts(definition, grant),
        max_iterations=3,
        runner=MagicMock(),
    )

    assert result.finish_reason is AgentRunFinishReason.MAX_ITERATIONS
    assert result.iterations_used == 3
    assert agent_llm.complete_agent_turn.await_count == 3
    assert result.error["error"] == "max_iterations_reached"


@pytest.mark.asyncio
async def test_a_provider_failure_ends_the_run_instead_of_retrying_forever(
    tracer, tenant_id
) -> None:
    definition = build_definition([])
    grant = ResolvedToolGrant(tools=[], allow_agent_delegation=False, delegate_agent_ids=[])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(
        side_effect=DomainValidationException(message="llm_provider_error")
    )
    repository = _agent_run_repository()

    result = await _loop(agent_llm, _dispatcher([]), repository, tracer).run(
        scope=_scope(tenant_id),
        definition=definition,
        grant=grant,
        prompt_parts=_prompt_parts(definition, grant),
        max_iterations=5,
        runner=MagicMock(),
    )

    assert result.finish_reason is AgentRunFinishReason.LLM_ERROR
    assert agent_llm.complete_agent_turn.await_count == 1
    event_types = {call.kwargs["event_type"] for call in repository.append_event.await_args_list}
    assert ExecutionEventType.LLMCallFailed in event_types


@pytest.mark.asyncio
async def test_a_denied_tool_call_is_logged_as_a_denial_event(tracer, tenant_id) -> None:
    definition = build_definition([build_tool("search")])
    grant = ResolvedToolGrant(
        tools=definition.tools, allow_agent_delegation=False, delegate_agent_ids=[]
    )
    denied = ToolCallOutcome(
        tool_call_id="c1",
        function_name="wire_transfer",
        status=AgentToolCallStatus.DENIED,
        result_text='{"error": "tool_not_authorized_for_this_run"}',
        error={"error": "tool_not_authorized_for_this_run"},
    )
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(
        side_effect=[
            _completion(
                tool_calls=[AgentToolCall(call_id="c1", name="wire_transfer", arguments={})]
            ),
            _completion(text="I cannot do that."),
        ]
    )
    repository = _agent_run_repository()

    result = await _loop(agent_llm, _dispatcher([denied]), repository, tracer).run(
        scope=_scope(tenant_id),
        definition=definition,
        grant=grant,
        prompt_parts=_prompt_parts(definition, grant),
        max_iterations=5,
        runner=MagicMock(),
    )

    assert result.finish_reason is AgentRunFinishReason.FINAL_OUTPUT
    event_types = [call.kwargs["event_type"] for call in repository.append_event.await_args_list]
    assert ExecutionEventType.ToolInvocationDenied in event_types


@pytest.mark.asyncio
async def test_the_transcript_is_persisted_before_the_first_turn(tracer, tenant_id) -> None:
    definition = build_definition([])
    grant = ResolvedToolGrant(tools=[], allow_agent_delegation=False, delegate_agent_ids=[])
    agent_llm = MagicMock()
    agent_llm.complete_agent_turn = AsyncMock(return_value=_completion(text="done"))
    repository = _agent_run_repository()

    await _loop(agent_llm, _dispatcher([]), repository, tracer).run(
        scope=_scope(tenant_id),
        definition=definition,
        grant=grant,
        prompt_parts=_prompt_parts(definition, grant),
        max_iterations=5,
        runner=MagicMock(),
    )

    sources = [call.kwargs.get("source") for call in repository.append_message.await_args_list]
    assert "agent_system_prompt" in sources
    assert "runtime_rules" in sources
    assert "task_instruction" in sources
