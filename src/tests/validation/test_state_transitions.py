import pytest

from domain.execution.services.state_machine import (
    RunLifecycleStateMachine,
    FlowRunStatus,
    ToolRunStatus,
)
from exceptions.service_exceptions import InvalidTransitionException


def test_invalid_flow_transition_blocked():
    lifecycle = RunLifecycleStateMachine()
    with pytest.raises(InvalidTransitionException):
        lifecycle.apply_transition("flow", FlowRunStatus.WAITING, FlowRunStatus.CREATED)


def test_tool_error_terminal():
    lifecycle = RunLifecycleStateMachine()
    next_status = lifecycle.apply_transition("tool", ToolRunStatus.EXECUTING, ToolRunStatus.ERROR)
    assert next_status == ToolRunStatus.ERROR
