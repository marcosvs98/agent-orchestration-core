"""Closed lifecycle transitions per run type.

`apply_transition(kind, current, target)` was replaced by per-kind `validate_*` methods that raise
on an illegal move and return None on a legal one.
"""

import pytest

from domain.execution.services.state_machine import (
    AgentRunStatus,
    FlowRunStatus,
    NodeRunStatus,
    RunLifecycleStateMachine,
    ToolRunStatus,
)
from exceptions.service_exceptions import InvalidTransitionException


def test_invalid_flow_transition_blocked():
    lifecycle = RunLifecycleStateMachine()

    with pytest.raises(InvalidTransitionException, match="Invalid FlowRun transition"):
        lifecycle.validate_flow(FlowRunStatus.WAITING, FlowRunStatus.CREATED)


def test_waiting_may_resume_to_running():
    RunLifecycleStateMachine().validate_flow(FlowRunStatus.WAITING, FlowRunStatus.RUNNING)


def test_tool_error_is_terminal():
    lifecycle = RunLifecycleStateMachine()

    lifecycle.validate_tool(ToolRunStatus.EXECUTING, ToolRunStatus.ERROR)

    with pytest.raises(InvalidTransitionException, match="Invalid ToolRun transition"):
        lifecycle.validate_tool(ToolRunStatus.ERROR, ToolRunStatus.EXECUTING)


@pytest.mark.parametrize(
    ("terminal", "validate", "target"),
    [
        (FlowRunStatus.COMPLETED, "validate_flow", FlowRunStatus.RUNNING),
        (FlowRunStatus.FAILED, "validate_flow", FlowRunStatus.RUNNING),
        (NodeRunStatus.COMPLETED, "validate_node", NodeRunStatus.RUNNING),
        (AgentRunStatus.COMPLETED, "validate_agent", AgentRunStatus.RUNNING),
        (ToolRunStatus.SUCCESS, "validate_tool", ToolRunStatus.EXECUTING),
    ],
)
def test_terminal_states_have_no_outgoing_transitions(terminal, validate, target):
    lifecycle = RunLifecycleStateMachine()

    with pytest.raises(InvalidTransitionException):
        getattr(lifecycle, validate)(terminal, target)
