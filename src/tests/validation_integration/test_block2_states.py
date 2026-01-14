from __future__ import annotations

import pytest

from domain.execution.services.state_machine import (
    AgentRunStatus,
    FlowRunStatus,
    NodeRunStatus,
    RunLifecycleStateMachine,
)
from exceptions.service_exceptions import InvalidTransitionException
from .evidence import text_block, write_markdown

pytestmark = [pytest.mark.validation_integration, pytest.mark.asyncio]


async def test_canonical_state_transitions() -> None:
    machine = RunLifecycleStateMachine()
    machine.validate_flow(FlowRunStatus.CREATED, FlowRunStatus.RUNNING)
    machine.validate_node(NodeRunStatus.PENDING, NodeRunStatus.RUNNING)
    machine.validate_agent(AgentRunStatus.CREATED, AgentRunStatus.RUNNING)
    with pytest.raises(InvalidTransitionException):
        machine.validate_flow(FlowRunStatus.COMPLETED, FlowRunStatus.RUNNING)
    with pytest.raises(InvalidTransitionException):
        machine.validate_node(NodeRunStatus.COMPLETED, NodeRunStatus.PENDING)
    with pytest.raises(InvalidTransitionException):
        machine.validate_agent(AgentRunStatus.FAILED, AgentRunStatus.RUNNING)

    diagram = (
        "### Flow runtime diagram\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        "flowCreated[FlowCreated] --> flowRunning[FlowRunning]\n"
        "flowRunning --> flowWaiting[FlowWaiting]\n"
        "flowRunning --> flowCompleted[FlowCompleted]\n"
        "flowRunning --> flowFailed[FlowFailed]\n"
        "flowRunning --> flowEscalated[FlowEscalated]\n"
        "flowWaiting --> flowRunning\n"
        "flowWaiting --> flowFailed\n"
        "flowWaiting --> flowEscalated\n"
        "flowCompleted --> flowTerminal[Terminal]\n"
        "flowFailed --> flowTerminal\n"
        "flowEscalated --> flowTerminal\n"
        "```\n"
    )
    write_markdown(
        "runtime-execution-diagram.md",
        [
            text_block(
                "Canonical transitions",
                "Transitions accept only the allowed edges; invalid moves raise InvalidTransitionException.",
            ),
            diagram,
        ],
    )
