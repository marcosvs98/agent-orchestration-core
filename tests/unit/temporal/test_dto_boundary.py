"""Guards the Temporal payload boundary.

Node state, memory, tool catalogues and user input stay in Postgres. Only
identifiers and control flags cross into workflow history, which is what keeps
history flat regardless of flow size. A `dict` or `Any` field on any of these
DTOs would silently reopen that door.
"""

from __future__ import annotations

import typing

import pytest

from adapters.temporal import dtos
from domain.execution.schemas.execution import FlowFailureReason
from domain.execution.services.graph_runtime.types import NodeExecutionStatus
from domain.execution.services.state_machine import RunStatus

BOUNDARY_MODELS = [
    dtos.FlowRunWorkflowInput,
    dtos.FlowRunPlanSummary,
    dtos.ExecuteNodeInput,
    dtos.ExecuteNodeOutput,
    dtos.FinalizeFlowRunInput,
    dtos.FlowRunWorkflowResult,
    dtos.FlowRunProgress,
]


@pytest.mark.parametrize("model", BOUNDARY_MODELS, ids=lambda m: m.__name__)
def test_no_open_payload_fields_cross_the_boundary(model) -> None:
    for name, field in model.model_fields.items():
        rendered = str(field.annotation)
        assert "dict" not in rendered.lower(), f"{model.__name__}.{name} carries a dict"
        assert "Any" not in rendered, f"{model.__name__}.{name} carries Any"


def test_node_status_literals_match_domain_enum() -> None:
    literals = set(typing.get_args(dtos.NodeStatusLiteral))
    assert literals == {member.value for member in NodeExecutionStatus}


def test_outcome_literals_are_representable_in_the_run_status_enum() -> None:
    literals = set(typing.get_args(dtos.OutcomeLiteral))
    assert literals <= {member.value for member in RunStatus} | {"WAITING"}


def test_failure_reason_strings_round_trip_to_the_domain_enum() -> None:
    for member in FlowFailureReason:
        assert FlowFailureReason(member.value) is member


def test_workflow_id_is_derived_from_the_flow_run_id() -> None:
    assert dtos.workflow_id_for("abc") == "flow-run-abc"
