import contextlib
from unittest.mock import MagicMock

import pytest

from domain.execution.services.state_machine import ExecutionStateMachine, RunStatus
from exceptions.service_exceptions import InvalidTransitionException


def _tracer() -> MagicMock:
    t = MagicMock()
    t.observe.side_effect = lambda **_: contextlib.nullcontext(MagicMock())
    return t


class TestExecutionStateMachine:
    def test_valid_transition_created_to_queued(self):
        machine = ExecutionStateMachine(_tracer())
        machine.validate_transition(RunStatus.CREATED, RunStatus.QUEUED)

    def test_valid_transition_queued_to_running(self):
        machine = ExecutionStateMachine(_tracer())
        machine.validate_transition(RunStatus.QUEUED, RunStatus.RUNNING)

    def test_valid_transition_running_to_completed(self):
        machine = ExecutionStateMachine(_tracer())
        machine.validate_transition(RunStatus.RUNNING, RunStatus.COMPLETED)

    def test_valid_transition_running_to_failed(self):
        machine = ExecutionStateMachine(_tracer())
        machine.validate_transition(RunStatus.RUNNING, RunStatus.FAILED)

    def test_valid_transition_running_to_waiting_input(self):
        machine = ExecutionStateMachine(_tracer())
        machine.validate_transition(RunStatus.RUNNING, RunStatus.WAITING_INPUT)

    def test_valid_transition_waiting_input_to_running(self):
        machine = ExecutionStateMachine(_tracer())
        machine.validate_transition(RunStatus.WAITING_INPUT, RunStatus.RUNNING)

    def test_invalid_transition_created_to_running(self):
        machine = ExecutionStateMachine(_tracer())
        with pytest.raises(InvalidTransitionException):
            machine.validate_transition(RunStatus.CREATED, RunStatus.RUNNING)

    def test_invalid_transition_completed_to_running(self):
        machine = ExecutionStateMachine(_tracer())
        with pytest.raises(InvalidTransitionException):
            machine.validate_transition(RunStatus.COMPLETED, RunStatus.RUNNING)

    def test_invalid_transition_failed_to_running(self):
        machine = ExecutionStateMachine(_tracer())
        with pytest.raises(InvalidTransitionException):
            machine.validate_transition(RunStatus.FAILED, RunStatus.RUNNING)

    def test_invalid_transition_cancelled_to_running(self):
        machine = ExecutionStateMachine(_tracer())
        with pytest.raises(InvalidTransitionException):
            machine.validate_transition(RunStatus.CANCELLED, RunStatus.RUNNING)
